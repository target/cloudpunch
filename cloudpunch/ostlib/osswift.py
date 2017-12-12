import logging
import os
import requests

from requests.packages.urllib3.exceptions import InsecureRequestWarning

from swiftclient import client as sclient

import exceptions

# Hide warnings about making insecure connections
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class BaseSwift(object):

    def __init__(self, session, cacert=None, insecure=False):
        self.sclient = sclient.Connection(session=session, cacert=cacert, insecure=insecure)


class Container(BaseSwift):

    def create(self, name):
        self.sclient.put_container(name)
        self.swift = name
        logging.debug('Created swift container %s', name)

    def create_object(self, filename, name=None, container_name=None, content_type='text/plain'):
        cname = self.get(container_name)
        oname = name if name else os.path.basename(filename)
        if not os.path.isfile(filename):
            raise exceptions.OSTLibError('File %s does not exist', filename)
        with open(filename, 'r') as f:
            self.sclient.put_object(cname,
                                    oname,
                                    contents=f.read(),
                                    content_type=content_type)
        logging.debug('Created object %s in container %s', oname, cname)

    def delete(self, name=None):
        cname = self.get(name)
        try:
            self.empty_container(cname)
            self.sclient.delete_container(cname)
            logging.debug('Deleted swift container %s', cname)
            return True
        except Exception as e:
            logging.error('Failed to delete swift container %s: %s' % (cname, e))
            return False

    def delete_object(self, name, container_name=None):
        cname = self.get(container_name)
        try:
            self.sclient.delete_object(cname, name)
            logging.debug('Deleted object %s in container %s', name, cname)
            return True
        except Exception as e:
            logging.error('Failed to delete swift container object %s inside %s: %s' % (name, cname, e))
            return False

    def empty_container(self, name=None):
        cname = self.get(name)
        objs = self.list_objects(cname)
        for obj in objs:
            logging.debug('Deleting object %s', obj['name'])
            self.delete_object(name, obj['name'])
        logging.debug('Container %s has been emptied', cname)

    def load(self, name):
        self.swift = name

    def list(self):
        containers = self.sclient.get_account()[1]
        container_info = []
        for container in containers:
            container_info.append({
                'id': container,
                'name': container,
            })
        return container_info

    def list_objects(self, container_name=None):
        return self.sclient.get_container(self.get(container_name))[1]

    def save_object(self, name, filename, container_name=None):
        cname = self.get(container_name)
        obj_tuple = self.sclient.get_object(cname, name)
        with open(filename, 'w') as f:
            f.write(obj_tuple[1])
        logging.debug('Saved object %s from container %s to %s', name, cname, filename)

    def get(self, name=None):
        if name:
            return name
        try:
            return self.swift
        except AttributeError:
            raise exceptions.OSTLibError('No swift container supplied and no cached container')

    def get_object(self, name, container_name=None):
        return self.sclient.get_object(self.get(container_name), name)

    def get_name(self):
        return self.get()

    def get_id(self):
        return self.get_name()
