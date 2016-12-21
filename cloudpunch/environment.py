import os
import yaml
import logging


class Environment(object):

    def __init__(self, env_file=None):

        # Hard coded default configuration
        # This should be enough to run a test without giving a config file
        default_config = {
            'image_name': 'CentOS7',
            'public_key_file': '~/.ssh/id_rsa.pub',
            'api_versions': {
                'cinder': 2,
                'neutron': 2,
                'nova': 2
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
                    'type': ''
                },
                'boot_from_vol': {
                    'enable': False,
                    'size': 10
                },
                'userdata': []
            },
            'client': {
                'flavor': 'm1.small',
                'availability_zone': '',
                'volume': {
                    'enable': False,
                    'size': 10,
                    'type': ''
                },
                'boot_from_vol': {
                    'enable': False,
                    'size': 10
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
                "git clone https://github.com/target/cloudpunch.git /opt/cloudpunch"
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
        self.final_config = default_config.copy()
        self.final_config.update(read_config)

    def loadconfig(self, env_file):
        contents = open(env_file).read()
        try:
            data = yaml.load(contents)
        except yaml.YAMLError as e:
            raise EnvError(e)
        return data

    def get_config(self):
        return self.final_config


class EnvError(Exception):
    pass
