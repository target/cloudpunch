import os
import logging
import time
import json
import random

import cloudpunch.utils.config as cpc
import cloudpunch.utils.metrics as metrics

from threading import Thread

METRIC_NAME = 'cloudpunch.iperf'
BPS_METRIC = '%s.bps' % METRIC_NAME
RETRAN_METRIC = '%s.retransmits' % METRIC_NAME


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
                'iperf': {
                    'bps_min': 100000,
                    'bps_max': 100000000,
                    'duration_min': 10,
                    'duration_max': 30,
                    'iterations': 10,
                    'threads': 1,
                    'max_throughput': True,
                    'mss': 1460
                }
            }
            self.config = cpc.merge_configs(default_config, self.config)
            self.runtest()
        except Exception as e:
            # Send exceptions back to control
            logging.error('%s: %s' % (type(e).__name__, e.message))
            self.final_results = '%s: %s' % (type(e).__name__, e.message)

    def runtest(self):
        # Start iperf in server mode
        if self.config['role'] == 'server' and self.config['server_client_mode']:
            logging.info('Starting iperf process in server and daemon mode')
            self.final_results.append('ServerMode')
            os.popen('iperf3 -s -D')

        # Start iperf in client mode
        else:
            if self.config['server_client_mode']:
                server_ip = self.config['match_ip']
            elif 'target' in self.config['iperf']:
                server_ip = self.config['iperf']['target']
            else:
                raise ConfigError('iPerf is running client mode but is missing a target server')

            logging.info('Starting iperf process in client mode connecting to %s', server_ip)
            # Wait 5 seconds to make sure iPerf servers have time to start
            time.sleep(5)

            # Check for and initialize iperf perams
            for i in range(self.config['iperf']['iterations']):
                logging.info('Running iteration %s of %s', i + 1, self.config['iperf']['iterations'])
                threads = self.config['iperf']['threads']
                duration = random.randint(self.config['iperf']['duration_min'], self.config['iperf']['duration_max'])
                mss = self.config['iperf']['mss']

                # Max throughput
                if self.config['iperf']['max_throughput']:
                    command = 'iperf3 -c %s -i 1 -t %s -P %s -J -M %s' % (server_ip, duration, threads, mss)

                # Variable throughput
                else:
                    bps = random.randint(self.config['iperf']['bps_min'], self.config['iperf']['bps_max'])
                    command = 'iperf3 -c %s -i 1 -t %s -b %sM -P %s -J -M %s' % (server_ip, duration, bps, threads, mss)

                self.run_iperf(command)

            # Send back summary if not over time
            if not self.config['overtime_results']:
                bps = [d['bps'] for d in self.final_results]
                retransmits = [d['retransmits'] for d in self.final_results]
                self.final_results = {
                    'bps': sum(bps) / len(bps),
                    'retransmits': sum(retransmits) / len(retransmits)
                }

    def run_iperf(self, command):
        logging.info('Running iperf command: %s', command)
        results = os.popen(command).read()
        # Remove new lines
        results = results.replace('\n', '')
        # Remove tabs
        results = results.replace('\t', '')
        results = json.loads(results)

        time_stamp = results['start']['timestamp']['timesecs']
        for i in results['intervals']:
            self.final_results.append({
                'time': time_stamp,
                'bps': i['sum']['bits_per_second'],
                'retransmits': i['sum']['retransmits']
            })
            if self.config['metrics']['enable']:
                self.metric.send_metric(BPS_METRIC, i['sum']['bits_per_second'], time_stamp)
                self.metric.send_metric(RETRAN_METRIC, i['sum']['retransmits'], time_stamp)
            time_stamp += 1

        logging.info('Completed iperf command: %s', command)


class ConfigError(Exception):

    def __init__(self, message):
        super(ConfigError, self).__init__(message)
        self.message = message
