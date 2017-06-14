import time
import logging

import glanceclient.client as gclient


class BaseImage(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the glance object which handles interaction with the API
        self.glance = gclient.Client(str(api_version),
                                     session=session,
                                     region_name=region_name)
        self.session = session
        self.api_version = api_version


class Image(BaseImage):

    def create(self, image_name, image_format, image_file):
        # Upload an image to glance from a file
        image_data = open(image_file, 'rb')
        logging.debug('Uploading image %s from file %s', image_name, image_file)
        self.image = self.glance.images.create(name=image_name,
                                               container_format='bare',
                                               disk_format=image_format)
        self.glance.images.upload(self.get_id(), image_data)
        logging.debug('Uploaded image %s with ID %s', image_name, self.get_id())

    def delete(self, image_id=None):
        image = self.get(image_id)
        try:
            self.glance.images.delete(image.id)
            logging.debug('Deleted image %s with ID %s', image.name, image.id)
            return True
        except Exception:
            logging.error('Failed to delete image %s with ID %s', image.name, image.id)
            return False

    def wait_for_active(self, image_id=None):
        image = self.get(image_id)
        for _ in range(300):
            img = self.get(image_id)
            if img.status.lower() == 'active':
                break
            time.sleep(1)
        img = self.get(image_id)
        if img.status.lower() != 'active':
            raise OSImageError('Image %s with ID %s took too long to change to active state' % (image.name,
                                                                                                image.id))
        logging.debug('Image %s with ID %s now in active state', image.name, image.id)

    def reactivate(self, image_id=None):
        image = self.get(image_id)
        self.glance.images.reactivate(image.id)
        logging.debug('Reactivated image %s', image.id)

    def deactivate(self, image_id=None):
        image = self.get(image_id)
        self.glance.images.deactivate(image.id)
        logging.debug('Deactivated image %s', image.id)

    def load(self, image_id):
        self.image = self.glance.images.get(image_id)

    def list(self, project_id=None, all_projects=False, include_public=False):
        images = self.glance.images.list()
        image_info = []
        for image in images:
            if image.visibility == 'public' and not include_public:
                continue
            if not all_projects and project_id and image.owner != project_id:
                continue
            if not all_projects and not project_id and image.owner != self.session.get_project_id():
                continue
            image_info.append({
                'id': image.id,
                'name': image.name,
                'owner': image.owner,
                'public': image.visibility == 'public'
            })
        return image_info

    def get(self, image_id=None, use_cached=False):
        if image_id:
            return self.glance.images.get(image_id)
        try:
            if use_cached:
                return self.image
            return self.glance.images.get(self.get_id())
        except AttributeError:
            raise OSImageError('No image supplied and no cached image')

    def get_name(self, image_id=None, use_cached=False):
        image = self.get(image_id, use_cached)
        return image.name

    def get_id(self, image_name=None, include_public=True):
        if image_name:
            images = self.glance.images.list()
            for image in images:
                if image.visibility == 'public' and not include_public:
                    continue
                if image.name == image_name:
                    return image.id
            raise OSImageError('Image %s was not found' % image_name)
        image = self.get(use_cached=True)
        return image.id


class OSImageError(Exception):

    def __init__(self, message):
        super(OSImageError, self).__init__(message)
        self.message = message
