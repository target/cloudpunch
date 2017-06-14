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
            raise OSUserError('Failed SSL verification to Keystone')
        except TypeError as e:
            # This is used to catch keys that keystone auth does not accept
            if "'" in e.message:
                raise OSUserError('Invalid auth info sent to Keystone. Was not expecting %s' % e.message[46:])
            else:
                raise OSUserError('Invalid auth info sent to Keystone')

    def get_session(self):
        return self.session


class BaseUser(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the keystone object which handles interaction with the API
        self.keystone = kclient.Client(session=session,
                                       region_name=region_name)
        self.api_version = api_version


class User(BaseUser):

    def create(self, name, password, project_id, email=None, description=None):
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

    def delete(self, user_id=None):
        user = self.get(user_id)
        # Delete the user
        try:
            user.delete()
            logging.debug('Deleted user %s with ID %s', user.name, user.id)
            return True
        except Exception:
            logging.error('Failed to delete user %s with ID %s', user.name, user.id)
            return False

    def add_to_project(self, project_id, role_id, user_id=None):
        user = self.get(user_id)
        if self.api_version == 2:
            self.keystone.roles.add_user_role(user.id, role_id, project_id)
        else:
            self.keystone.roles.grant(role_id, user=user.id, project=project_id)
        logging.debug('Added role %s to user %s for the project %s', role_id, user.id, project_id)

    def remove_from_project(self, project_id, role_id, user_id=None):
        user = self.get(user_id)
        if self.api_version == 2:
            self.keystone.roles.remove_user_role(user.id, role_id, project_id)
        else:
            self.keystone.roles.revoke(role_id, user=user.id, project=project_id)
        logging.debug('Removed role %s from user %s for the project %s', role_id, user.id, project_id)

    def load(self, user_id):
        # Load in a user
        self.user = self.keystone.users.get(user_id)

    def list(self, project_id=None, domain=None, group=None):
        user_info = []
        if project_id:
            if self.api_version == 2:
                raise OSUserError('Cannot search for users on project on Keystone v2')
            assignments = self.keystone.role_assignments.list(project=project_id)
            for assignment in assignments:
                user_info.append({
                    'role': assignment.role['id'],
                    'id': assignment.user['id']
                })
        else:
            if self.api_version == 2:
                users = self.keystone.users.list()
            else:
                users = self.keystone.users.list(domain=domain, group=group)
            for user in users:
                user_info.append({
                    'id': user.id,
                    'name': user.name
                })
        return user_info

    def get(self, user_id=None, use_cached=False):
        if user_id:
            return self.keystone.users.get(user_id)
        try:
            if use_cached:
                return self.user
            return self.keystone.users.get(self.get_id())
        except AttributeError:
            raise OSUserError('No user supplied and no cached user')

    def get_name(self, user_id=None, use_cached=False):
        user = self.get(user_id, use_cached)
        return user.name

    def get_id(self):
        user = self.get(use_cached=True)
        return user.id


class Project(BaseUser):

    def create(self, name, description=None):
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

    def delete(self, project_id=None):
        project = self.get(project_id)
        # Delete the tenant / project
        try:
            project.delete()
            logging.debug('Deleted tenant/project %s with ID %s', project.name, project.id)
            return True
        except Exception:
            logging.debug('Failed to delete tenant/project %s with ID %s', project.name, project.id)
            return False

    def load(self, project_id):
        # Load in a tenant / project
        if self.api_version == 2:
            self.project = self.keystone.tenants.get(project_id)
        elif self.api_version == 3:
            self.project = self.keystone.projects.get(project_id)

    def list(self):
        if self.api_version == 2:
            projects = self.keystone.tenants.list()
        elif self.api_version == 3:
            projects = self.keystone.projects.list()
        project_info = []
        for project in projects:
            project_info.append({
                'id': project.id,
                'name': project.name
            })
        return project_info

    def get(self, project_id=None, use_cached=False):
        if project_id:
            if self.api_version == 2:
                return self.keystone.tenants.get(project_id)
            elif self.api_version == 3:
                return self.keystone.projects.get(project_id)
        try:
            if use_cached:
                return self.project
            else:
                if self.api_version == 2:
                    return self.keystone.tenants.get(self.get_id())
                elif self.api_version == 3:
                    return self.keystone.projects.get(self.get_id())
        except AttributeError:
            raise OSUserError('No project supplied and no cached project')

    def get_name(self, project_id=None, use_cached=False):
        project = self.get(project_id, use_cached)
        return project.name

    def get_id(self):
        project = self.get(use_cached=True)
        return project.id


class Role(BaseUser):

    def list(self):
        role_info = []
        roles = self.keystone.roles.list()
        for role in roles:
            role_info.append({
                'id': role.id,
                'name': role.name
            })
        return role_info


class Domain(BaseUser):

    def list(self):
        domain_info = []
        domains = self.keystone.domains.list()
        for domain in domains:
            domain_info.append({
                'id': domain.id,
                'name': domain.name
            })
        return domain_info

    def get(self, domain_id=None, use_cached=False):
        if self.api_version == 2:
            raise OSUserError('Keystone v2 does not support domains')
        if domain_id:
            return self.keystone.domains.get(domain_id)
        try:
            if use_cached:
                return self.domain
            else:
                return self.keystone.domains.get(self.get_id())
        except AttributeError:
            raise OSUserError('No domain supplied and no cached domain')

    def get_name(self, domain_id=None):
        domain = self.get(domain_id)
        return domain.name


class OSUserError(Exception):

    def __init__(self, message):
        super(OSUserError, self).__init__(message)
        self.message = message
