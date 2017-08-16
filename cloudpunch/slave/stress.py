import os
import logging
import collections
import random
import time

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
                    'cpu-min': 1,
                    'cpu-max': 2,
                    'duration-min': 5,
                    'duration-max': 10,
                    'load-min': 25,
                    'load-max': 90,
                    'iterations': 5,
                    'delay': 5
                }
            }
            self.merge_configs(default_config, self.config)
            self.config = default_config
            self.runtest()
        except Exception as e:
            # Send exceptions back to master
            logging.error('%s: %s', type(e).__name__, e.message)
            self.final_results = '%s: %s' % (type(e).__name__, e.message)

    def runtest(self):
        for i in range(self.config['stress']['iterations']):
            logging.info('Running iteration %s of %s', i, self.config['stress']['iterations'])

            # Generate random numbers based on min/max configuration
            cpu = random.randint(self.config['stress']['cpu-min'], self.config['stress']['cpu-max'])
            timeout = random.randint(self.config['stress']['duration-min'], self.config['stress']['duration-max'])
            load = random.randint(self.config['stress']['load-min'], self.config['stress']['load-max'])

            results = {
                'cpu': [],
                'timeout': [],
                'load': []
            }
            # Over time results
            if self.config['overtime_results']:
                self.final_results.append({
                    'cpu': cpu,
                    'timeout': timeout,
                    'load': load
                })
            # Summary results
            else:
                results['cpu'].append(cpu)
                results['timeout'].append(timeout)
                results['load'].append(load)

            command = 'nice -n %s stress-ng --cpu %s --timeout %ss --cpu-load %s' % (self.config['stress']['nice'],
                                                                                     cpu,
                                                                                     timeout,
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
                    'cpu': sum(results['cpu']) / len(results['cpu']),
                    'timeout': sum(results['timeout']) / len(results['timeout']),
                    'load': sum(results['load']) / len(results['load'])
                }
            except ZeroDivisionError:
                self.final_results = {
                    'cpu': -1,
                    'timeout': -1,
                    'load': -1
                }

    def merge_configs(self, default, new):
        for key, value in new.iteritems():
            if (key in default and isinstance(default[key], dict) and
                    isinstance(new[key], collections.Mapping)):
                self.merge_configs(default[key], new[key])
            else:
                default[key] = new[key]
