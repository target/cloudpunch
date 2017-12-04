import re
import subprocess
import logging
import time

import cloudpunch.utils.config as cpc
import cloudpunch.utils.metrics as metrics

from threading import Thread

METRIC_NAME = 'cloudpunch.ping'
LATENCY_METRIC = '%s.latency' % METRIC_NAME


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = []
        if self.config['metrics']['enable']:
            self.metric = metrics.Metrics(self.config['metrics'])
        super(CloudPunchTest, self).__init__()

    def run(self):
        try:
            default_config = {
                'ping': {
                    'target': 'google.com',
                    'duration': 10
                }
            }
            self.config = cpc.merge_configs(default_config, self.config)
            self.runtest()
        except Exception as e:
            # Send exceptions back to control
            logging.error('%s: %s', type(e).__name__, e.message)
            self.final_results = '%s: %s' % (type(e).__name__, e.message)

    def runtest(self):
        # Configuration setup
        if self.config['server_client_mode']:
            server_ip = self.config['match_ip']
        else:
            server_ip = self.config['ping']['target']
        duration = str(self.config['ping']['duration'])

        logging.info('Starting ping command to server %s for %s seconds', server_ip, duration)
        ping = subprocess.Popen(['ping', '-c', duration, server_ip],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        for line in iter(ping.stdout.readline, ''):
            latency = re.findall(r'time=(\d+\.\d+)', line)
            now = int(time.time())
            latency = float(latency[0]) if latency else 0
            self.final_results.append({
                'time': now,
                'latency': latency
            })
            if self.config['metrics']['enable']:
                self.metric.send_metric(LATENCY_METRIC, latency, now)

        ping.stdout.close()

        # Send back summary if not over time
        if not self.config['overtime_results']:
            latency = [d['latency'] for d in self.final_results]
            self.final_results = {
                'latency': sum(latency) / len(latency)
            }
