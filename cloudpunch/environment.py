import os
import yaml
import logging
import collections


class Environment(object):

    def __init__(self, env_file=None):

        # Hard coded default configuration
        # This should be enough to run a test without giving a config file
        default_config = {
            'image_name': 'CentOS7',
            'public_key_file': '~/.ssh/id_rsa.pub',
            'api_versions': {
                'cinder': 2,
                'glance': 2,
                'neutron': 2,
                'nova': 2,
                'lbaas': 2
            },
            'master': {
                'flavor': 'm1.small',
                'availability_zone': '',
                'userdata': [
                    "systemctl start redis.service"
                ]
            },
            'server': {
                'flavor': 'm1.small',
                'availability_zone': '',
                'volume': {
                    'enable': False,
                    'size': 10,
                    'type': '',
                    'availability_zone': ''
                },
                'boot_from_vol': {
                    'enable': False,
                    'size': 10
                },
                'loadbalancer': {
                    'enable': False,
                    'method': 'ROUND_ROBIN',
                    'frontend': {
                        'protocol': 'HTTP',
                        'port': 80
                    },
                    'backend': {
                        'protocol': 'HTTP',
                        'port': 80
                    },
                    'healthmonitor': {
                        'type': 'PING',
                        'delay': 5,
                        'timeout': 5,
                        'retries': 3,
                        'url_path': '/',
                        'http_method': 'GET',
                        'expected_codes': '200'
                    }
                },
                'userdata': []
            },
            'client': {
                'flavor': 'm1.small',
                'availability_zone': '',
                'volume': {
                    'enable': False,
                    'size': 10,
                    'type': '',
                    'availability_zone': ''
                },
                'boot_from_vol': {
                    'enable': False,
                    'size': 10
                },
                'loadbalancer': {
                    'enable': False,
                    'method': 'ROUND_ROBIN',
                    'frontend': {
                        'protocol': 'HTTP',
                        'port': 80
                    },
                    'backend': {
                        'protocol': 'HTTP',
                        'port': 80
                    },
                    'healthmonitor': {
                        'type': 'PING',
                        'delay': 5,
                        'timeout': 5,
                        'retries': 3,
                        'url_path': '/',
                        'http_method': 'GET',
                        'expected_codes': '200'
                    }
                },
                'userdata': []
            },
            'secgroup_rules': [
                ['icmp', -1, -1],
                ['tcp', 80, 80]
            ],
            'dns_nameservers': [
                '8.8.8.8',
                '8.8.4.4'
            ],
            'shared_userdata': [
                "mkdir -p /opt/cloudpunch",
                "git clone https://github.com/target/cloudpunch.git /opt/cloudpunch",
                "cd /opt/cloudpunch",
                "python setup.py install"
            ],
            'external_network': '',
        }
        read_config = {}

        # Load configuration from file if specified
        if env_file:
            if not os.path.isfile(env_file):
                raise EnvError('Environment config file %s not found' % env_file)
            logging.debug('Loading environment config from file %s', env_file)
            read_config = self.loadconfig(env_file)
        else:
            logging.debug('Using default CloudPunch environment configuration')

        # Merge default and config file
        self.merge_configs(default_config, read_config)
        self.final_config = default_config

        # Replace ~ with $HOME
        if self.final_config['public_key_file'][0] == '~':
            self.final_config['public_key_file'] = '%s%s' % (os.environ['HOME'],
                                                             self.final_config['public_key_file'][1:])

        # Error checking
        if not os.path.isfile(self.final_config['public_key_file']):
            raise EnvError('Public key file %s does not exist' % self.final_config['public_key_file'])

    def merge_configs(self, default, new):
        for key, value in new.iteritems():
            if (key in default and isinstance(default[key], dict) and
                    isinstance(new[key], collections.Mapping)):
                self.merge_configs(default[key], new[key])
            else:
                default[key] = new[key]

    def loadconfig(self, env_file):
        with open(env_file) as f:
            contents = f.read()
        try:
            data = yaml.load(contents)
        except yaml.YAMLError as e:
            raise EnvError(e)
        return data

    def get_config(self):
        return self.final_config


class EnvError(Exception):

    def __init__(self, message):
        super(EnvError, self).__init__(message)
        self.message = message
