import os
import logging
import time
import json
import sysinfo
import datadog
import random

from threading import Thread


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = []
        super(CloudPunchTest, self).__init__()

    def run(self):
        try:
            # Start iperf in server mode
            if self.config['role'] == 'server' and self.config['server_client_mode']:
                logging.info('Starting iperf process in server and daemon mode')
                self.final_results.append('ServerMode')
                os.popen('iperf3 -s -D')

            # Start iperf in client mode
            elif self.config['role'] == 'client' or not self.config['server_client_mode']:
                server_ip = self.config['match_ip'] if self.config['server_client_mode'] else self.config['iperf']['target']
                logging.info('Starting iperf process in client mode connecting to %s', server_ip)
                # Wait 5 seconds to make sure iPerf servers have time to start
                time.sleep(5)
                if not self.config['overtime_results']:
                    self.results = {
                        'bps': [],
                        'retransmits': []
                    }

                # Check for and initialize iperf perams
                for i in range(self.config['iperf']['iterations']):
                    logging.info('Running iteration %s of %s', i + 1, self.config['iperf']['iterations'])
                    threads = self.config['iperf']['threads']
                    duration = random.randint(self.config['iperf']['duration_min'], self.config['iperf']['duration_max'])
                    mss = self.config['iperf']['mss']

                    # Max throughput
                    if self.config['iperf']['max_throughput']:
                        command = 'iperf3 -c %s -i 1 -t %s -P %s -J -M %s' % (server_ip, duration, threads, mss)
                        self.run_iperf(command)

                    # Variable throughput
                    else:
                        bps = random.randint(self.config['iperf']['bps_min'], self.config['iperf']['bps_max'])
                        command = 'iperf3 -c %s -i 1 -t %s -b %sM -P %s -J -M %s' % (server_ip, duration, bps, threads, mss)
                        self.run_iperf(command)

                # Average out results if we don't want overtime results
                if not self.config['overtime_results']:
                    self.final_results = {
                        'bps': sum(self.results['bps']) / len(self.results['bps']),
                        'retransmits': sum(self.results['retransmits']) / len(self.results['retransmits'])
                    }

        except Exception as e:
            # Send exceptions back to master
            logging.error('%s: %s' % (type(e).__name__, e.message))
            self.final_results = '%s: %s' % (type(e).__name__, e.message)

    def run_iperf(self, command):
        logging.info('Running iperf command: %s', command)
        results = os.popen(command).read()
        # Remove new lines
        results = results.replace('\n', '')
        # Remove tabs
        results = results.replace('\t', '')
        results = json.loads(results)
        if self.config['overtime_results']:
            time_stamp = results['start']['timestamp']['timesecs']
            for i in results['intervals']:
                self.final_results.append({
                    'time': time_stamp,
                    'bps': i['sum']['bits_per_second'],
                    'retransmits': i['sum']['retransmits']
                })
                time_stamp += 1
        else:
            for i in results['intervals']:
                self.results['bps'].append(i['sum']['bits_per_second'])
                self.results['retransmits'].append(i['sum']['retransmits'])
        logging.info('Completed iperf command: %s', command)
        if self.config['datadog']['enable']:
            self.send_datadog_results(results)

    def send_datadog_results(self, results):
        # Datadog setup
        hostname = sysinfo.hostname()
        options = {
            'api_key': self.config['datadog']['api_key']
        }
        datadog.initialize(**options)
        time_stamp = results['start']['timestamp']['timesecs']
        # Parse JSON output and send to Datadog
        for i in results['intervals']:
            metric_bps = i['sum']['bits_per_second']
            retransmits = i['sum']['retransmits']
            # Submit a point with a host and tags
            try:
                datadog.api.Metric.send(metric='osperf.iperf.thrps',
                                        points=(time_stamp, metric_bps),
                                        host=hostname,
                                        tags=self.config['datadog']['tags'])
                datadog.api.Metric.send(metric='osperf.iperf.retransmits',
                                        points=(time_stamp, retransmits),
                                        host=hostname,
                                        tags=self.config['datadog']['tags'])
            except Exception as e:
                logging.error('Failed to write to datadog: %s', e.message)
            time_stamp += 1
