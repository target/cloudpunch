import logging

import keystoneauth1 as kauth
import keystoneauth1.identity.v2 as kid2
import keystoneauth1.identity.v3 as kid3
from keystoneclient import client as kclient


class Session(object):

    def __init__(self, creds, verify=True):
        auth = creds.get_auth()
        # Figure out Keystone auth version
        if creds.get_version() == 3:
            identity = kid3.Token(**auth) if 'token' in auth else kid3.Password(**auth)
        else:
            identity = kid2.Token(**auth) if 'token' in auth else kid2.Password(**auth)
        # keystone session verify is either True, False, or a String for cacert
        if verify and creds.get_cacert():
            verify = creds.get_cacert()
        try:
            # Create the keystone session
            # This also verifies authentication
            self.session = kauth.session.Session(auth=identity,
                                                 verify=verify)
        except kauth.exceptions.http.Unauthorized:
            raise OSUserError('Failed to authenticate to Keystone')
        except kauth.exceptions.connection.SSLError:
            raise OSUserError('Failed SSL verification. Use --insecure to ignore')
        except TypeError as e:
            # This is used to catch keys that keystone auth does not accept
            if "'" in e.message:
                raise OSUserError('Invalid auth info sent to Keystone. Was not expecting %s' % e.message[46:])
            else:
                raise OSUserError('Invalid auth info sent to Keystone')

    def get_session(self):
        return self.session


class User(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the keystone object which handles interaction with the API
        self.keystone = kclient.Client(session=session,
                                       region_name=region_name)
        self.api_version = api_version

    def create_user(self, name, password, project_id, email=None, description=None):
        if self.api_version == 2:
            # Create user on version 2
            self.user = self.keystone.users.create(name=name,
                                                   password=password,
                                                   description=description,
                                                   email=email,
                                                   tenant_id=project_id,
                                                   enabled=True)
            logging.debug('Created user %s with ID %s under tenant ID %s', name, self.get_id(), project_id)
        elif self.api_version == 3:
            # Create user on version 3
            self.user = self.keystone.users.create(name=name,
                                                   password=password,
                                                   description=description,
                                                   email=email,
                                                   default_project=project_id,
                                                   enabled=True)
            logging.debug('Created user %s with ID %s under project ID %s', name, self.get_id(), project_id)

    def delete_user(self):
        # Delete the user
        try:
            self.user.delete()
            logging.debug('Deleted user %s with ID %s', self.get_name(), self.get_id())
            return True
        except Exception:
            logging.error('Failed to delete user %s with ID %s', self.get_name(), self.get_id())
            return False

    def load_user(self, user_id):
        # Load in a user
        self.user = self.keystone.users.get(user_id)

    def get_name(self):
        return self.user['name']

    def get_id(self):
        return self.user['id']


class Project(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the keystone object which handles interaction with the API
        self.keystone = kclient.Client(session=session,
                                       region_name=region_name)
        self.api_version = api_version

    def create_project(self, name, description=None):
        if self.api_version == 2:
            # Create tenant for version 2
            self.project = self.keystone.tenants.create(tenant_name=name,
                                                        description=description,
                                                        enabled=True)
            logging.debug('Created tenant %s with ID %s', name, self.get_id())
        elif self.api_version == 3:
            # Create project for version 3
            self.project = self.keystone.projects.create(name=name,
                                                         description=description,
                                                         enabled=True)
            logging.debug('Created project %s with ID %s', name, self.get_id())

    def delete_project(self):
        # Delete the tenant / project
        try:
            self.project.delete()
            logging.debug('Deleted tenant/project %s with ID %s', self.get_name(), self.get_id())
            return True
        except Exception:
            logging.debug('Failed to delete tenant/project %s with ID %s', self.get_name(), self.get_id())
            return False

    def load_project(self, project_id):
        # Load in a tenant / project
        if self.api_version == 2:
            self.project = self.keystone.tenants.get(project_id)
        elif self.api_version == 3:
            self.project = self.keystone.projects.get(project_id)

    def get_name(self):
        return self.project['name']

    def get_id(self):
        return self.project['id']


class OSUserError(Exception):
    pass
