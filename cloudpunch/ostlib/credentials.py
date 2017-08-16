import os
import re
import logging
import getpass


class Credentials(object):

    def __init__(self, openrc_file=None, password=None, no_env=False, interactive=False, use_admin=False):
        """
        Handles loading OpenStack credentials from the environment and OpenRC files

        Parameters
        ----------
        openrc_file : str
            file path to an OpenRC file
        password : str
            password to authenticate to OpenStack
        no_env : bool
            do not load from environment if True
        interactive : bool
            ask user for password if not found in environment and OpenRC file if True
        use_admin : bool
            ignore if project or tenant information is missing if True
        """
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
                raise CredError('Project information is missing from OpenRC file and environment')

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
            password = ''
            while len(password) == 0:
                ask_str = 'Enter your OpenStack %s for %s on region %s: ' % (auth_type,
                                                                             self.creds['auth_url'],
                                                                             self.creds['region_name'])
                password = getpass.getpass(ask_str)
            self.creds[auth_type] = password

        # Set API version to 3 if needed
        if self.creds['auth_url'][-2:] == 'v3':
            self.api_version = 3

    def loadrc(self, openrc_file):
        """
        Load in an OpenRC file into the credentials attribute

        Parameters
        ----------
        openrc_file : str
            file path to an OpenRC file
        """
        logging.debug('Loading OpenStack authentication information from file %s', openrc_file)
        with open(openrc_file, 'r') as f:
            contents = f.read()
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
        """
        Load OpenStack credentials from the environment into the credentials attribute
        """
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
        """
        Returns the full credentials attribute

        Returns
        -------
        dict
            The full credentials attribute, contains all OS_ based variables found in
            OpenRC files and the environment
        """
        return self.creds

    def get_auth(self):
        """
        Returns only the required credentials information for the Keystone API version

        Returns
        -------
        dict
            The required credentials for the Keystone API version
        """
        # Only return accepted keys from the auth_keys dictionary
        # This is to prevent exceptions thrown from keystone session
        returnDict = {}
        for key in self.creds:
            if key in self.auth_keys[self.api_version]:
                returnDict[key] = self.creds[key]
        return returnDict

    def get_version(self):
        """
        Returns the Keystone API version

        Returns
        -------
        int
            The Keystone API version
        """
        return self.api_version

    def get_region(self):
        """
        Returns the OpenStack region

        Returns
        -------
        str
            The OpenStack region
        """
        return self.creds.get('region_name')

    def get_cacert(self):
        """
        Returns the path to the ca certificate

        Returns
        -------
        str
            Path to the ca certificate
        """
        return self.creds.get('cacert')

    def get_project(self):
        """
        Returns the project/tenant id or name (if id is not in the credentials attribute)

        Returns
        -------
        str
            The project/tenant id or name
        """
        if self.api_version == 2:
            return self.creds.get('tenant_id') or self.creds.get('tenant_name')
        else:
            return self.creds.get('project_id') or self.creds.get('project_name')

    def get_project_specific(self, project_format='id'):
        """
        Returns a specific project/tenant id or name based on project_format

        Parameters
        ----------
        project_format : str
            id or name, specifies what format to return

        Returns
        -------
        str
            The project/tenant id or name (based on project_format)
        """
        if self.api_version == 2:
            return self.creds.get('tenant_%s' % project_format)
        else:
            return self.creds.get('project_%s' % project_format)

    def change_project(self, project, project_format='id'):
        """
        Changes the credentials attribute to change the tenant/project id or name. It will delete the
        opposite of project_format

        Parameters
        ----------
        project : str
            name or id of the new project/tenant
        project_format : str
            id or name, specifies what format to change
        """
        name = 'tenant' if self.api_version == 2 else 'project'
        self.creds['%s_%s' % (name, project_format)] = project
        opposite_format = 'name' if project_format == 'id' else 'id'
        del self.creds['%s_%s' % (name, opposite_format)]

    def change_user(self, username, password):
        """
        Changes the credentials attribute to change the user and password

        Parameters
        ----------
        username : str
            the new username
        password : str
            the new password
        """
        self.creds['username'] = username
        self.creds['password'] = password

    def change_user_domain(self, user_domain, domain_format='name'):
        """
        Change the credentials attribute for a new user domain name/id

        Parameters
        ----------
        user_domain : str
            the new user domain name/id (based on domain_format)
        domain_format : str
            name or id, specifies what format to change
        """
        self.creds['user_domain_%s' % domain_format] = user_domain


class CredError(Exception):

    def __init__(self, message):
        super(CredError, self).__init__(message)
        self.message = message
