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
            cores = random.randint(self.config['stress']['cores-min'], self.config['stress']['cores-max'])
            duration = random.randint(self.config['stress']['duration-min'], self.config['stress']['duration-max'])
            load = random.randint(self.config['stress']['load-min'], self.config['stress']['load-max'])

            results = {
                'cores': [],
                'duration': [],
                'load': []
            }
            # Over time results
            if self.config['overtime_results']:
                self.final_results.append({
                    'cores': cores,
                    'duration': duration,
                    'load': load
                })
            # Summary results
            else:
                results['cores'].append(cores)
                results['duration'].append(duration)
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
                    'duration': sum(results['duration']) / len(results['duration']),
                    'load': sum(results['load']) / len(results['load'])
                }
            except ZeroDivisionError:
                self.final_results = {
                    'cores': -1,
                    'duration': -1,
                    'load': -1
                }

    def merge_configs(self, default, new):
        for key, value in new.iteritems():
            if (key in default and isinstance(default[key], dict) and
                    isinstance(new[key], collections.Mapping)):
                self.merge_configs(default[key], new[key])
            else:
                default[key] = new[key]
