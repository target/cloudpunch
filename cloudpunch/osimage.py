import time
import logging

import glanceclient.client as gclient


class Image(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the glance object which handles interaction with the API
        self.glance = gclient.Client(str(api_version),
                                     session=session,
                                     region_name=region_name)
        self.api_version = api_version

    def upload_image(self, image_name, image_file):
        # Upload an image to glance from a file
        logging.debug('Uploading image %s from file %s', image_name, image_file)
        self.image = self.glance.images.upload(image_name, image_file)
        logging.debug('Uploaded image %s with ID %s', image_name, self.get_id())

    def delete_image(self):
        self.glance.delete(self.get_id())
        logging.debug('Deleted image %s with ID %s', self.get_name(), self.get_id())

    def wait_for_active(self):
        for _ in range(300):
            img = self.glance.images.get(self.get_id())
            if img.status.lower() == 'active':
                break
            time.sleep(1)
        img = self.glance.images.get(self.get_id())
        if img.status.lower() != 'active':
            raise OSImageError('Image %s with ID %s took too long to change to active state' % (self.get_name,
                                                                                                self.get_id()))
        logging.debug('Image %s with ID %s now in active state', self.get_name(), self.get_id())

    def load_image(self, image_id):
        self.image = self.glance.images.get(image_id)

    def get_id(self):
        return self.image.id

    def get_name(self):
        return self.image.name


class OSImageError(Exception):
    pass
