import os
import logging
import random
import time

import cloudpunch.utils.config as cpc

from threading import Thread


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = []
        super(CloudPunchTest, self).__init__()

    def run(self):
        try:
            default_config = {
                'stress': {
                    'nice': 0,
                    'cores_min': 1,
                    'cores_max': 2,
                    'duration_min': 5,
                    'duration_max': 10,
                    'load_min': 25,
                    'load_max': 90,
                    'iterations': 5,
                    'delay': 5
                }
            }
            self.config = cpc.merge_configs(default_config, self.config)
            self.runtest()
        except Exception as e:
            # Send exceptions back to master
            logging.error('%s: %s', type(e).__name__, e.message)
            self.final_results = '%s: %s' % (type(e).__name__, e.message)

    def runtest(self):
        for i in range(self.config['stress']['iterations']):
            logging.info('Running iteration %s of %s', i, self.config['stress']['iterations'])

            # Generate random numbers based on min/max configuration
            cores = random.randint(self.config['stress']['cores_min'], self.config['stress']['cores_max'])
            duration = random.randint(self.config['stress']['duration_min'], self.config['stress']['duration_max'])
            load = random.randint(self.config['stress']['load_min'], self.config['stress']['load_max'])

            results = {
                'cores': [],
                'load': []
            }
            # Over time results
            if self.config['overtime_results']:
                self.final_results.append({
                    'cores': cores,
                    'time': int(time.time()),
                    'load': load
                })
            # Summary results
            else:
                results['cores'].append(cores)
                results['load'].append(load)

            command = 'nice -n %s stress-ng --cpu %s --timeout %ss --cpu-load %s' % (self.config['stress']['nice'],
                                                                                     cores,
                                                                                     duration,
                                                                                     load)
            logging.info('Running stress command: %s', command)
            os.popen(command)
            logging.info('Stress command complete')
            logging.info('Sleeping for %s seconds', self.config['stress']['delay'])
            time.sleep(self.config['stress']['delay'])

        # Send back summary if not over time
        if not self.config['overtime_results']:
            try:
                self.final_results = {
                    'cores': sum(results['cores']) / len(results['cores']),
                    'load': sum(results['load']) / len(results['load'])
                }
            except ZeroDivisionError:
                self.final_results = {
                    'cores': -1,
                    'load': -1
                }


class ConfigError(Exception):

    def __init__(self, message):
        super(ConfigError, self).__init__(message)
        self.message = message
