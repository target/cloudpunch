import time
import logging


class BaseVolume(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Import here to avoid cinder api_versions from calling logging.basicConfig
        import cinderclient.client as cclient
        # Create the keystone object which handles interaction with the API
        self.cinder = cclient.Client(str(api_version),
                                     session=session,
                                     region_name=region_name)
        self.api_version = api_version


class Volume(BaseVolume):

    def create(self, size, name, volume_type=None, availability_zone=None, description=None):
        if self.api_version == 1:
            # Create a volume on version 1
            self.volume = self.cinder.volumes.create(size,
                                                     display_name=name,
                                                     display_description=description,
                                                     availability_zone=availability_zone,
                                                     volume_type=volume_type)
        else:
            # Create a volume on version 2 and 3
            self.volume = self.cinder.volumes.create(size,
                                                     name=name,
                                                     description=description,
                                                     availability_zone=availability_zone,
                                                     volume_type=volume_type)
        logging.debug('Created volume %s with ID %s', name, self.get_id())
        logging.debug('Waiting for volume %s with ID %s to become available', name, self.get_id())
        # Wait 10 seconds for the volume to become available
        for _ in range(10):
            volume = self.cinder.volumes.get(self.get_id())
            if volume.status == 'available':
                break
            elif volume.status == 'error':
                raise OSVolumeError('Volume %s with ID %s failed to create' % (name, self.get_id()))
            elif volume.status == 'creating':
                time.sleep(1)
        volume = self.cinder.volumes.get(self.get_id())
        # Check if the volume became available
        if volume.status != 'available':
            raise OSVolumeError('Volume %s with ID %s took too long to become available' % (name, self.get_id()))
        logging.debug('Volume %s with ID %s is now available', name, self.get_id())

    def delete(self, volume_id=None, force=False):
        volume = self.get(volume_id)
        # Wait 10 seconds for the volume to delete
        for _ in range(10):
            try:
                if force:
                    self.cinder.volumes.force_delete(volume.id)
                else:
                    self.cinder.volumes.delete(volume.id)
                logging.debug('Deleted volume %s with ID %s', volume.name, volume.id)
                return True
            except Exception:
                time.sleep(1)
        # The volume has failed to delete
        logging.error('Failed to delete volume %s with ID %s', volume.name, volume.id)
        return False

    def load(self, volume_id):
        # Load in a volume
        self.volume = self.cinder.volumes.get(volume_id)

    def list(self, project_id=None, all_projects=False):
        if not project_id and not all_projects:
            volumes = self.cinder.volumes.list()
        else:
            volumes = []
            volumes_chunk = self.cinder.volumes.list(search_opts={"all_tenants": 1},
                                                     limit=1000)
            while len(volumes_chunk) > 0:
                volumes += volumes_chunk
                volumes_chunk = self.cinder.volumes.list(search_opts={"all_tenants": 1},
                                                         limit=1000,
                                                         marker=volumes_chunk[-1].id)
        volume_info = []
        for volume in volumes:
            if project_id and project_id != volume.to_dict()['os-vol-tenant-attr:tenant_id']:
                continue
            volume_info.append({
                'id': volume.id,
                'name': volume.name,
            })
        return volume_info

    def list_availability_zones(self):
        return self.cinder.availability_zones.list()

    def get(self, volume_id=None, use_cached=False):
        if volume_id:
            return self.cinder.volumes.get(volume_id)
        try:
            if use_cached:
                return self.volume
            return self.cinder.volumes.get(self.get_id())
        except AttributeError:
            raise OSVolumeError('No volume supplied and no cached volume')

    def get_name(self, volume_id=None, use_cached=False):
        volume = self.get(volume_id, use_cached)
        return volume.display_name if self.api_version == 1 else volume.name

    def get_id(self):
        volume = self.get(use_cached=True)
        return volume.id


class Snapshot(BaseVolume):

    def create(self, volume_id, name, description='', force=False):
        if self.api_version == 1:
            self.snapshot = self.cinder.volume_snapshots.create(volume_id,
                                                                force=force,
                                                                display_name=name,
                                                                display_description=description)
        else:
            self.snapshot = self.cinder.volume_snapshots.create(volume_id,
                                                                force=force,
                                                                name=name,
                                                                description=description)
        logging.debug('Created volume snapshot %s with ID %s from volume %s', name, self.get_id(), volume_id)
        logging.debug('Waiting for volume snapshot %s with ID %s to become available', name, self.get_id())
        # Wait 60 seconds for the snapshot to become available
        for _ in range(60):
            snapshot = self.cinder.volume_snapshots.get(self.get_id())
            if snapshot.status == 'available':
                break
            elif snapshot.status == 'error':
                raise OSVolumeError('Volume snapshot %s with ID %s failed to create' % (name, self.get_id()))
            time.sleep(1)
        snapshot = self.cinder.volume_snapshots.get(self.get_id())
        # Check if the snapshot became available
        if snapshot.status != 'available':
            raise OSVolumeError('Volume snapshot %s with ID %s took too long to become available' % (name,
                                                                                                     self.get_id()))
        logging.debug('Volume snapshot %s with ID %s is now available', name, self.get_id())

    def delete(self, snapshot_id=None, force=False):
        snapshot = self.get(snapshot_id)
        # Wait 10 seconds for the snapshot to delete
        for _ in range(10):
            try:
                self.cinder.volume_snapshots.delete(snapshot.id, force)
                logging.debug('Deleted volume snapshot %s with ID %s', snapshot.name, snapshot.id)
                return True
            except Exception:
                time.sleep(1)
        # The snapshot has failed to delete
        logging.error('Failed to delete volume snapshot %s with ID %s', snapshot.name, snapshot.id)
        return False

    def load(self, snapshot_id):
        self.snapshot = self.cinder.volume_snapshots.get(snapshot_id)

    def list(self, project_id=None, all_projects=False):
        if not project_id and not all_projects:
            snapshots = self.cinder.volume_snapshots.list()
        else:
            snapshots = []
            snapshot_chunk = self.cinder.volume_snapshots.list(search_opts={"all_tenants": 1},
                                                               limit=1000)
            while len(snapshot_chunk) > 0:
                snapshots += snapshot_chunk
                snapshot_chunk = self.cinder.volume_snapshots.list(search_opts={"all_tenants": 1},
                                                                   limit=1000,
                                                                   marker=snapshot_chunk[-1].id)
        snapshot_info = []
        for snapshot in snapshots:
            if project_id and project_id != snapshot.to_dict()['os-extended-snapshot-attributes:project_id']:
                continue
            snapshot_info.append({
                'id': snapshot.id,
                'name': snapshot.name
            })
        return snapshot_info

    def get(self, snapshot_id=None, use_cached=False):
        if snapshot_id:
            return self.cinder.volume_snapshots.get(snapshot_id)
        try:
            if use_cached:
                return self.snapshot
            return self.cinder.volume_snapshots.get(self.get_id())
        except AttributeError:
            raise OSVolumeError('No volume snapshot supplied no cached volume snapshot')

    def get_name(self, snapshot_id=None, use_cached=False):
        snapshot = self.get(snapshot_id, use_cached)
        return snapshot.display_name if self.api_version == 1 else snapshot.name

    def get_id(self):
        snapshot = self.get(use_cached=True)
        return snapshot.id


class Backup(BaseVolume):

    def create(self, volume_id, name, description='', container=None, snapshot_id=None, incremental=False, force=False):
        if self.api_version == 1:
            self.backup = self.cinder.backups.create(volume_id,
                                                     container=container,
                                                     force=force,
                                                     name=name,
                                                     description=description)
        else:
            self.backup = self.cinder.backups.create(volume_id,
                                                     container=container,
                                                     incremental=incremental,
                                                     force=force,
                                                     snapshot_id=snapshot_id,
                                                     name=name,
                                                     description=description)
        logging.debug('Created volume backup %s with ID %s from volume %s', name, self.get_id(), volume_id)
        logging.debug('Waiting for volume backup %s with ID %s to become available', name, self.get_id())
        # Wait 60 seconds for the backup to become available
        for _ in range(60):
            backup = self.cinder.backups.get(self.get_id())
            if backup.status == 'available':
                break
            elif backup.status == 'error':
                raise OSVolumeError('Volume backup %s with ID %s failed to create' % (name, self.get_id()))
            time.sleep(1)
        backup = self.cinder.backups.get(self.get_id())
        # Check if the backup became available
        if backup.status != 'available':
            raise OSVolumeError('Volume backup %s with ID %s took too long to become available' % (name, self.get_id()))
        logging.debug('Volume backup %s with ID %s is now available', name, self.get_id())

    def delete(self, backup_id=None, force=False):
        backup = self.get(backup_id)
        # Wait 10 seconds for the backup to delete
        for _ in range(10):
            try:
                self.cinder.backups.delete(backup.id, force)
                logging.debug('Deleted volume backup %s with ID %s', backup.name, backup.id)
                return True
            except Exception:
                time.sleep(1)
        # The backup has failed to delete
        logging.error('Failed to delete volume backup %s with ID %s', backup.name, backup.id)
        return False

    def load(self, backup_id):
        self.backup = self.cinder.backups.get(backup_id)

    def list(self, project_id=None, all_projects=False):
        if not project_id and not all_projects:
            backups = self.cinder.backups.list()
        else:
            backups = []
            backup_chunk = self.cinder.backups.list(search_opts={"all_tenants": 1},
                                                    limit=1000)
            while len(backup_chunk) > 0:
                backups += backup_chunk
                backup_chunk = self.cinder.backups.list(search_opts={"all_tenants": 1},
                                                        limit=1000,
                                                        marker=backup_chunk[-1].id)
        backup_info = []
        for backup in backups:
            backup_info.append({
                'id': backup.id,
                'name': backup.name
            })
        if project_id:
            volumes = []
            volumes_chunk = self.cinder.volumes.list(search_opts={"all_tenants": 1},
                                                     limit=1000)
            while len(volumes_chunk) > 0:
                volumes += volumes_chunk
                volumes_chunk = self.cinder.volumes.list(search_opts={"all_tenants": 1},
                                                         limit=1000,
                                                         marker=volumes_chunk[-1].id)
            volume_info = []
            for volume in volumes:
                if project_id != volume.to_dict()['os-vol-tenant-attr:tenant_id']:
                    continue
                volume_info.append({
                    'id': volume.id,
                    'name': volume.name,
                })
            for backup in backup_info:
                in_project = False
                for volume in volume_info:
                    if volume['id'] == self.get(backup['id']).volume_id:
                        in_project = True
                        break
                if not in_project:
                    backup_info.remove(backup)
        return backup_info

    def get(self, backup_id=None, use_cached=False):
        if backup_id:
            return self.cinder.backups.get(backup_id)
        try:
            if use_cached:
                return self.backup
            return self.cinder.backups.get(self.get_id())
        except AttributeError:
            raise OSVolumeError('No volume backup supplied no cached volume backup')

    def get_name(self, backup_id=None, use_cached=False):
        backup = self.get(backup_id, use_cached)
        return backup.display_name if self.api_version == 1 else backup.name

    def get_id(self):
        backup = self.get(use_cached=True)
        return backup.id


class Quota(BaseVolume):

    def get(self, project_id):
        return self.cinder.quotas.get(project_id).to_dict()

    def set(self, project_id, **quotas):
        self.cinder.quotas.update(project_id, **quotas)

    def set_defaults(self, project_id):
        self.cinder.quotas.defaults(project_id)


class OSVolumeError(Exception):

    def __init__(self, message):
        super(OSVolumeError, self).__init__(message)
        self.message = message
