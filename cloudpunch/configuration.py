import os
import yaml
import logging
import collections

# List of offical files inside cp_slave (not test files)
OFFICIAL_FILES = ['__init__', 'cp_slave', 'sysinfo', 'flaskapp']


class Configuration(object):

    def __init__(self, config_file=None, output_file=None, hostmap_file=None, flavor_file=None, split_mode=False):

        # Hard coded default configuration
        # This should be enough to run a test without giving a config file
        default_config = {
            'cleanup_resources': True,
            'server_client_mode': True,
            'servers_give_results': False,
            'overtime_results': False,
            'instance_threads': 5,
            'retry_count': 50,
            'network_mode': 'full',
            'number_routers': 1,
            'networks_per_router': 1,
            'instances_per_network': 1,
            'test': ['ping'],
            'test_mode': 'list',
            'test_start_delay': 0,
            'recovery': {
                'enable': False,
                'type': 'ask',
                'threshold': 80,
                'retries': 12
            }
        }
        read_config = {}

        # Load configuration from file if specified
        if config_file:
            if not os.path.isfile(config_file):
                raise ConfigError('Configuration file %s not found' % config_file)
            logging.debug('Loading configuration from file %s', config_file)
            read_config = self.loadfile(config_file, 'Configuration')
        else:
            logging.debug('Using default CloudPunch configuration')

        # Merge default and config file
        self.merge_configs(default_config, read_config)
        self.final_config = default_config

        # Check official tests (tests in slave/)
        slave_dir = os.path.dirname(os.path.realpath(__file__)) + '/slave'
        files = os.listdir(slave_dir)
        official_tests = []
        for filename in files:
            name, extension = os.path.splitext(filename)
            if extension == '.py' and name not in OFFICIAL_FILES:
                official_tests.append(name)
        # Check unofficial tests (tests in config)
        unofficial_tests = []
        for test in self.final_config['test']:
            if test not in official_tests:
                unofficial_tests.append(test)
        # We have unofficial tests to find in the tests directory (current-directory/tests)
        if unofficial_tests:
            self.final_config['test_files'] = {}
            test_dir = 'tests'
            for unofficial_test in unofficial_tests:
                test_file_path = '%s/%s.py' % (test_dir, unofficial_test)
                if not os.path.isfile(test_file_path):
                    raise ConfigError('Unable to find unofficial test %s in tests directory' % unofficial_test)
                with open(test_file_path) as f:
                    test_file_data = f.read()
                self.final_config['test_files'][unofficial_test] = test_file_data

        # Check if server_client_mode is enabled when split mode is enabled
        if split_mode and not self.final_config['server_client_mode']:
            raise ConfigError('server_client_mode is required be to enabled when split mode is enabled')
        # Split mode will only work in full network mode
        if split_mode and self.final_config['network_mode'] != 'full':
            raise ConfigError('network_mode must be full when split mode is enabled')

        # Add output_file to config if specified
        if output_file:
            logging.debug('Saving results to file %s', output_file)
            self.final_config['output_file'] = output_file

        # Add hostmap to config if specified
        if hostmap_file:
            if not os.path.isfile(hostmap_file):
                raise ConfigError('Hostmap file %s not found' % hostmap_file)
            logging.debug('Using hostmap file %s', hostmap_file)
            self.final_config['hostmap'] = self.loadfile(hostmap_file, 'Hostmap')

        # Add flavor file to config if specified
        if flavor_file:
            if not os.path.isfile(flavor_file):
                raise ConfigError('Flavor file %s not found' % flavor_file)
            flavor_data = self.loadfile(flavor_file, 'Flavor')['flavors']
            # Remove any zero percent flavors
            for flavor in flavor_data[:]:
                if float(flavor_data[flavor]) == 0.0:
                    del flavor_data[flavor]
            # Check if total percent is 99 to 100 (99 for 1/3)
            total = 0.0
            for flavor in flavor_data:
                total += float(flavor_data[flavor])
            if total > 100.0 or total < 99.0:
                raise ConfigError('Flavor file does not add up to 99-100%%. Currently %s%%' % total)
            logging.debug('Using flavor file %s', flavor_file)
            self.final_config['flavor_file'] = flavor_data

        # Add fio test_file to config if specified
        if ('fio' in self.final_config['test'] and
                'fio' in self.final_config and 'test_file' in self.final_config['fio'] and
                self.final_config['fio']['test_file']):
            test_file = self.final_config['fio']['test_file']
            if not os.path.isfile(test_file):
                raise ConfigError('FIO test file %s not found' % test_file)
            with open(test_file, 'r') as f:
                test_file_data = f.read()
            self.final_config['fio']['test_file_data'] = test_file_data

        # Check numbers in configuration
        if self.final_config['instance_threads'] < 1:
            raise ConfigError('Invalid number of instance_threads. Must be greater than 0')
        if self.final_config['test_start_delay'] < 0:
            raise ConfigError('Invalid test_start_delay. Must be 0 or greater')
        if self.final_config['retry_count'] < 1:
            raise ConfigError('Invalid retry_count. Must be greater than 0')
        if self.final_config['number_routers'] < 1:
            raise ConfigError('Invalid number_routers. Must be greater than 0')
        if self.final_config['networks_per_router'] < 1:
            raise ConfigError('Invalid networks_per_router. Must be greater than 0')
        if self.final_config['instances_per_network'] < 1:
            raise ConfigError('Invalid instances_per_network. Must be greater than 0')

        # Check test mode
        if self.final_config['test_mode'] not in ['list', 'concurrent']:
            raise ConfigError('Invalid test_mode. Must be list or concurrent')

        # Check recovery mode
        if self.final_config['recovery']['type'] not in ['ask', 'rebuild']:
            raise ConfigError('Invalid recovery type. Must be ask, continue, or rebuild')
        if self.final_config['recovery']['threshold'] < 0:
            raise ConfigError('Invalid recovery threshold. Must be 0 or greater')
        if self.final_config['recovery']['retries'] < 1:
            raise ConfigError('Invalid recovery retries. Must be greater than 0')

        # Network and environment number checks
        if self.final_config['network_mode'] not in ['full', 'single-router', 'single-network']:
            raise ConfigError('Invalid network_mode. Must be full, single-router, or single-network')
        if self.final_config['server_client_mode'] and self.final_config['number_routers'] > 126:
            raise ConfigError('Number of routers cannot be greater than 126 if server_client_mode is enabled')
        if self.final_config['number_routers'] > 254:
            raise ConfigError('Number of routers cannot be greater than 254')
        if self.final_config['networks_per_router'] > 254:
            raise ConfigError('Number of networks per router cannot be greater than 254')
        if self.final_config['network_mode'] == 'full':
            if self.final_config['instances_per_network'] > 250:
                raise ConfigError('Number of instances per network cannot be greater than 250')
        if self.final_config['network_mode'] in ['single-router', 'single-network']:
            if self.final_config['server_client_mode'] and self.final_config['networks_per_router'] > 126:
                raise ConfigError('Number of networks per router cannot be greater than 126'
                                  ' if server_client_mode is enabled')
            if self.final_config['instances_per_network'] > 62500:
                raise ConfigError('Number of instances per network cannot be greater than 62500'
                                  ' if network mode is single-router or single-network')

    def merge_configs(self, default, new):
        for key, value in new.iteritems():
            if (key in default and isinstance(default[key], dict) and
                    isinstance(new[key], collections.Mapping)):
                self.merge_configs(default[key], new[key])
            else:
                default[key] = new[key]

    def loadfile(self, data_file, label='Configuration'):
        with open(data_file) as f:
            contents = f.read()
        try:
            data = yaml.load(contents)
        except yaml.YAMLError as e:
            raise ConfigError('%s file failed to load: %s' (label, e))
        return data

    def get_config(self):
        return self.final_config


class ConfigError(Exception):

    def __init__(self, message):
        super(ConfigError, self).__init__(message)
        self.message = message
