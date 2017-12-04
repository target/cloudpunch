import logging
import requests

import cloudpunch.utils.config as cpc
import cloudpunch.utils.sysinfo as sysinfo

from threading import Thread
from urlparse import urlparse


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = {}
        super(CloudPunchTest, self).__init__()

    def run(self):
        try:
            default_config = {
                'swift': {
                    'direction': 'upload',
                    'download': {
                        'container': 'cloudpunch',
                        'file': 'cp-download-test'
                    },
                    'upload': {
                        'size_min': 102400000,
                        'size_max': 102400000
                    },
                    'duration': 60,
                    'iterations': 0
                }
            }
            self.config = cpc.merge_configs(default_config, self.config)
            self.runtest()
        except Exception as e:
            # Send exceptions back to control
            logging.error('%s: %s', type(e).__name__, e.message)
            self.final_results = '%s: %s' % (type(e).__name__, e.message)

    def runtest(self):
        # Determine which connection to use
        my_role = sysinfo.role()
        if my_role == 'server' and self.config['server_client_mode']:
            connect_role = 'client'
        else:
            connect_role = 'server'
        auth_url = urlparse(self.config['authurl'][connect_role]).netloc
        auth_token = self.config['authtoken'][connect_role]


class ConfigError(Exception):

    def __init__(self, message):
        super(ConfigError, self).__init__(message)
        self.message = message
