import time
import logging


class Volume(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Import here to avoid cinder api_versions from calling logging.basicConfig
        import cinderclient.client as cclient
        # Create the keystone object which handles interaction with the API
        self.cinder = cclient.Client(str(api_version),
                                     session=session,
                                     region_name=region_name)
        self.api_version = api_version

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

    def delete(self, volume_id=None):
        volume = self.get(volume_id)
        # Wait 10 seconds for the volume to delete
        for _ in range(10):
            try:
                self.cinder.volumes.force_delete(volume.id)
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

    def list(self, project_only=True):
        if project_only:
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
            volume_info.append({
                'id': volume.id,
                'name': volume.name
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


class Quota(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Import here to avoid cinder api_versions from calling logging.basicConfig
        import cinderclient.client as cclient
        # Create the keystone object which handles interaction with the API
        self.cinder = cclient.Client(str(api_version),
                                     session=session,
                                     region_name=region_name)
        self.api_version = api_version

    def get(self, tenant_id):
        return self.cinder.quotas.get(tenant_id).to_dict()

    def set(self, tenant_id, **quotas):
        self.cinder.quotas.update(tenant_id, **quotas)

    def set_defaults(self, tenant_id):
        self.cinder.quotas.defaults(tenant_id)


class OSVolumeError(Exception):

    def __init__(self, message):
        super(OSVolumeError, self).__init__(message)
        self.message = message
