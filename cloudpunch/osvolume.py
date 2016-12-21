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

    def create_volume(self, size, name, volume_type=None, availability_zone=None, description=None):
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

    def delete_volume(self):
        # Wait 10 seconds for the volume to delete
        for _ in range(10):
            try:
                self.cinder.volumes.force_delete(self.volume)
                logging.debug('Deleted volume %s with ID %s', self.get_name(), self.get_id())
                return True
            except Exception:
                time.sleep(1)
        # The volume has failed to delete
        logging.error('Failed to delete volume %s with ID %s', self.get_name(), self.get_id())
        return False

    def load_volume(self, volume_id):
        # Load in a volume
        self.volume = self.cinder.volumes.get(volume_id)

    def get_volume(self, volume_id=None):
        if volume_id:
            return self.cinder.volumes.get(volume_id).to_dict()
        if self.volume:
            return self.cinder.volumes.get(self.get_id()).to_dict()
        return None

    def get_id(self):
        return self.volume.id

    def get_name(self):
        return self.volume.display_name if self.api_version == 1 else self.volume.name

    def list_availability_zones(self):
        return self.cinder.availability_zones.list()

    def list_volumes(self):
        return self.cinder.volumes.list()


class Quota(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Import here to avoid cinder api_versions from calling logging.basicConfig
        import cinderclient.client as cclient
        # Create the keystone object which handles interaction with the API
        self.cinder = cclient.Client(str(api_version),
                                     session=session,
                                     region_name=region_name)
        self.api_version = api_version

    def get_quota(self, tenant_id):
        return self.cinder.quotas.get(tenant_id).to_dict()

    def set_quota(self, tenant_id, **quotas):
        self.cinder.quotas.update(tenant_id, **quotas)

    def set_defaults(self, tenant_id):
        self.cinder.quotas.defaults(tenant_id)


class OSVolumeError(Exception):
    pass
