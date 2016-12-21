import os
import logging
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
            if 'stress' not in self.config:
                logging.error('Missing stress configuration')
                self.final_results = 'Missing stress configuration'
            else:
                for i in range(self.config['stress']['iterations']):
                    logging.info('Running iteration %s of %s', i, self.config['stress']['iterations'])

                    # Generate random numbers based on min/max configuration
                    cpu = random.randint(self.config['stress']['cpu-min'], self.config['stress']['cpu-max'])
                    timeout = random.randint(self.config['stress']['duration-min'], self.config['stress']['duration-max'])
                    load = random.randint(self.config['stress']['load-min'], self.config['stress']['load-max'])

                    command = 'nice -n %s stress-ng --cpu %s --timeout %ss --cpu-load %s' % (self.config['stress']['nice'],
                                                                                             cpu,
                                                                                             timeout,
                                                                                             load)
                    logging.info('Running stress command: %s', command)
                    self.final_results.append({
                        'cpu': cpu,
                        'timeout': timeout,
                        'load': load
                    })
                    os.popen(command)
                    logging.info('Stress command complete')
                    logging.info('Sleeping for %s seconds', self.config['stress']['delay'])
                    time.sleep(self.config['stress']['delay'])
        except Exception as e:
            # Send exceptions back to master
            logging.error('%s: %s', type(e).__name__, e.message)
            self.final_results = '%s: %s' % (type(e).__name__, e.message)
