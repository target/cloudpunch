import re
import subprocess
import logging
import collections
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
                'ping': {
                    'target': 'google.com',
                    'duration': 10
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
        # Configuration setup
        target = self.config['match_ip'] if self.config['server_client_mode'] else self.config['ping']['target']
        duration = str(self.config['ping']['duration'])

        results = []
        logging.info('Starting ping command to server %s for %s seconds', target, duration)
        ping = subprocess.Popen(['ping', '-c', duration, target],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        for line in iter(ping.stdout.readline, ''):
            latency = re.findall(r'time=(\d+\.\d+)', line)
            now = time.time()
            if latency:
                latency = float(latency[0])
                # Over time results
                if self.config['overtime_results']:
                    self.final_results.append({
                        'time': now,
                        'latency': latency
                    })
                # Summary results
                else:
                    results.append(latency)
            # Ping failed
            elif 'Request timeout' in line and self.config['overtime_results']:
                self.final_results.append({
                    'time': now,
                    'latency': 0
                })

        ping.stdout.close()

        # Send back summary if not over time
        if not self.config['overtime_results']:
            try:
                self.final_results = {
                    'latency': sum(results) / len(results)
                }
            except ZeroDivisionError:
                self.final_results = {
                    'latency': -1
                }

    def merge_configs(self, default, new):
        for key, value in new.iteritems():
            if (key in default and isinstance(default[key], dict) and
                    isinstance(new[key], collections.Mapping)):
                self.merge_configs(default[key], new[key])
            else:
                default[key] = new[key]
