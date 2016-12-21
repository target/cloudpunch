import re
import subprocess
import logging
import sysinfo
import datadog
import time

from threading import Thread


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = []
        super(CloudPunchTest, self).__init__()

    def run(self):
        try:
            # Configuration setup
            if 'ping' in self.config and 'duration' in self.config['ping']:
                duration = str(self.config['ping']['duration'])
            else:
                duration = '10'
            if not self.config['server_client_mode']:
                if 'ping' in self.config and 'target' in self.config['ping']:
                    target = self.config['ping']['target']
                else:
                    target = 'google.com'
            else:
                target = self.config['match_ip']

            # Datadog setup
            if self.config['datadog']['enable']:
                hostname = sysinfo.hostname()
                options = {
                    'api_key': self.config['datadog']['api_key']
                }
                datadog.initialize(**options)

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
                            'target': target,
                            'latency': latency
                        })
                    # Summary results
                    else:
                        results.append(latency)
                    # Send out to datadog
                    if self.config['datadog']['enable']:
                        try:
                            datadog.api.Metric.send(metric='osperf.ping.latency',
                                                    points=(now, latency),
                                                    host=hostname,
                                                    tags=self.config['datadog']['tags'])
                        except Exception as e:
                            logging.error('Failed to write to datadog: %s', e.message)
                # Ping failed, report error if over time
                elif 'Request timeout' in line and self.config['overtime_results']:
                    self.final_results.append({
                        'time': now,
                        'target': target,
                        'error': 'timeout'
                    })

            ping.stdout.close()

            # Send back summary if not over time
            if not self.config['overtime_results']:
                try:
                    self.final_results = {
                        'target': target,
                        'duration': int(duration),
                        'latency': sum(results) / len(results)
                    }
                except ZeroDivisionError:
                    self.final_results = {
                        'target': target,
                        'duration': int(duration),
                        'latency': -1
                    }

        except Exception as e:
            # Send exceptions back to master
            logging.error('%s: %s', type(e).__name__, e.message)
            self.final_results = '%s: %s' % (type(e).__name__, e.message)
