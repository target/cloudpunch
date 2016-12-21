import os
import re
import logging
import getpass


class Credentials(object):

    def __init__(self, openrc_file=None, password=None, no_env=False, interactive=False, use_admin=False):
        self.creds = {}
        self.api_version = 2
        # List of accepted keys for Keystone version 2 and 3
        self.auth_keys = {
            2: ['auth_url', 'username', 'password', 'token', 'user_id', 'trust_id', 'tenant_id', 'tenant_name'],
            3: ['auth_url', 'username', 'password', 'token', 'token_id', 'user_id', 'user_domain_id',
                'user_domain_name', 'trust_id', 'domain_id', 'domain_name', 'project_id', 'project_name',
                'project_domain_id', 'project_domain_name']
        }

        # Make sure we have something to load from
        if not openrc_file and no_env:
            raise CredError('No OpenRC file specified and no environment flag set. No credentials to load')

        # Load in OpenRC file
        if openrc_file:
            if not os.path.isfile(openrc_file):
                raise CredError('OpenRC file %s not found' % openrc_file)
            self.loadrc(openrc_file)

        # Load in environment if no_env is False
        if not no_env:
            self.loadenv()

        # Set password if specified
        if password:
            if 'username' in self.creds:
                self.creds['password'] = password
            else:
                self.creds['token'] = password

        # Check for required credentials
        if 'auth_url' not in self.creds:
            raise CredError('OS_AUTH_URL is missing from OpenRC file and environment')

        # Check for project if admin mode is disabled
        if not use_admin:
            found = False
            for name in ['tenant_name', 'tenant_id', 'project_name', 'project_id']:
                if name in self.creds:
                    found = True
            if not found:
                raise CredError('Project information is missing from OpenRC file and environment and admin mode is disabled')

        # Warn if no region_name
        if 'region_name' not in self.creds:
            logging.warning('OS_REGION_NAME is missing from OpenRC file and environment. May cause issues')
            self.creds['region_name'] = None

        # Password is used when there is a username, otherwise it needs a token
        auth_type = 'password'
        if 'username' not in self.creds:
            auth_type = 'token'

        if auth_type not in self.creds:
            # Fail out if interactive is false
            if not interactive:
                raise CredError('OS_PASSWORD and OS_TOKEN missing from OpenRC file and environment')
            # Ask user for password / token if we don't have one
            password = getpass.getpass('Enter your OpenStack %s for %s on region %s: ' % (auth_type,
                                                                                          self.creds['auth_url'],
                                                                                          self.creds['region_name']))
            while len(password) == 0:
                password = getpass.getpass('Enter your OpenStack %s for %s on region %s: ' % (auth_type,
                                                                                              self.creds['auth_url'],
                                                                                              self.creds['region_name']))
            self.creds[auth_type] = password

        # Set API version to 3 if needed
        if self.creds['auth_url'][-2:] == 'v3':
            self.api_version = 3

    def loadrc(self, openrc_file):
        logging.debug('Loading OpenStack authentication information from file %s', openrc_file)
        contents = open(openrc_file).read()
        # Regex to find export OS_****=****
        export_re = re.compile('export OS_([A-Z_]*)="?(.*)')
        for line in contents.splitlines():
            line = line.strip()
            mstr = export_re.match(line)
            if mstr:
                # OS_**** is index 1 (only the *'s)
                # after = is index 2
                name = mstr.group(1)
                value = mstr.group(2)
                # Take out ending "
                if value.endswith('"'):
                    value = value[:-1]
                # Ignore any dynamic values
                if value.startswith('$'):
                    continue
                # Don't print out password or token to debug
                if 'PASSWORD' not in name or 'TOKEN' not in name:
                    logging.debug('Using %s from OpenRC file for OS_%s', value, name)
                self.creds[name.lower()] = value

    def loadenv(self):
        logging.debug('Loading OpenStack authentication information from environment')
        # Grab any OS_ found in environment
        for var in os.environ:
            if var[0:3] == 'OS_':
                value = os.environ[var]
                # Don't print out password or token to debug
                if 'PASSWORD' not in var or 'TOKEN' not in var:
                    logging.debug('Using %s from environment for %s', value, var)
                self.creds[var[3:].lower()] = value

    def get_creds(self):
        return self.creds

    def get_auth(self):
        # Only return accepted keys from the auth_keys dictionary
        # This is to prevent exceptions thrown from keystone session
        returnDict = {}
        for key in self.creds:
            if key in self.auth_keys[self.api_version]:
                returnDict[key] = self.creds[key]
        return returnDict

    def get_version(self):
        return self.api_version

    def get_region(self):
        if 'region_name' in self.creds:
            return self.creds['region_name']
        return None

    def get_cacert(self):
        if 'cacert' in self.creds:
            return self.creds['cacert']
        return None

    def get_project(self):
        if self.api_version == 2:
            return self.creds['tenant_id'] if 'tenant_id' in self.creds else self.creds['tenant_name']
        elif self.api_version == 3:
            return self.creds['project_id'] if 'project_id' in self.creds else self.creds['project_name']

    def change_user(self, username, password, project_name):
        self.creds['username'] = username
        self.creds['password'] = password
        if self.api_version == 3:
            self.creds['project_name'] = project_name
        else:
            self.creds['tenant_name'] = project_name


class CredError(Exception):
    pass
