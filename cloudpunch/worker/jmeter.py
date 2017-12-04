import os
import subprocess
import xmltodict
import logging
import time

import cloudpunch.utils.config as cpc
import cloudpunch.utils.metrics as metrics

from threading import Thread

WORKER_PATH = os.path.dirname(os.path.realpath(__file__))
ORIGINAL_JMETER_FILE = '%s/jmeter-test.jmx' % WORKER_PATH
NEW_JMETER_FILE = '%s/generated-jmeter-test.jmx' % WORKER_PATH

METRIC_NAME = 'cloudpunch.jmeter'
RPS_METRIC = '%s.rps' % METRIC_NAME
LATENCY_METRIC = '%s.latency' % METRIC_NAME
ECOUNT_METRIC = '%s.ecount' % METRIC_NAME
EPERCENT_METRIC = '%s.epercent' % METRIC_NAME


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
                'jmeter': {
                    'threads': 10,
                    'ramp_up': 0,
                    'duration': 60,
                    'port': 80,
                    'path': '/api/system/health',
                    'gunicorn': {
                        'workers': 5,
                        'threads': 4
                    }
                }
            }
            self.config = cpc.merge_configs(default_config, self.config)
            self.runtest()
        except Exception as e:
            # Send exceptions back to control
            self.final_results = '%s: %s' % (type(e).__name__, e.message)
            logging.error(self.final_results)

    def runtest(self):
        # Start the gunicorn Flask webserver
        if self.config['role'] == 'server' and self.config['server_client_mode']:
            workers = self.config['jmeter']['gunicorn']['workers']
            threads = self.config['jmeter']['gunicorn']['threads']
            logging.info('Starting the gunicorn Flask app with %s workers and %s threads',
                         workers, threads)
            os.popen('gunicorn -D --bind 0.0.0.0:80 --pythonpath %s flaskapp:app -w %s --threads %s' % (WORKER_PATH,
                                                                                                        workers,
                                                                                                        threads))
            self.final_results = 'ServerMode'

        # Start jmeter
        else:
            if self.config['server_client_mode']:
                server_ip = self.config['match_ip']
            elif 'target' in self.config['jmeter']:
                server_ip = self.config['jmeter']['target']
            else:
                raise ConfigError('Missing target IP address in jmeter configuration')
            self.write_jmeter_config(self.config['jmeter'], server_ip)

            # Wait 5 seconds for the server to start
            time.sleep(5)

            jmeter_command = 'jmeter -n -t %s' % (NEW_JMETER_FILE)
            logging.info('Running the jmeter command: %s', jmeter_command)
            popen = subprocess.Popen(jmeter_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

            for line in iter(popen.stdout.readline, b''):
                line = line.strip()
                if '+' not in line:
                    continue
                # Remove excess white spaces
                line = ' '.join(line.split()).split()

                now = int(time.time())
                rps = float(line[6][:-2])
                latency = int(line[8])
                ecount = int(line[14])
                epercent = float(filter(lambda x: x not in '()%', line[15]))

                self.final_results.append({
                    'time': now,
                    'rps': rps,
                    'latency': latency,
                    'ecount': ecount,
                    'epercent': epercent
                })

                if self.config['metrics']['enable']:
                    self.metric.send_metric(RPS_METRIC, rps, now)
                    self.metric.send_metric(LATENCY_METRIC, latency, now)
                    self.metric.send_metric(ECOUNT_METRIC, ecount, now)
                    self.metric.send_metric(EPERCENT_METRIC, epercent, now)

            popen.stdout.close()

            # Send back summary if not over time
            if not self.config['overtime_results']:
                rps = [d['rps'] for d in self.final_results]
                latency = [d['latency'] for d in self.final_results]
                ecount = [d['ecount'] for d in self.final_results]
                epercent = [d['epercent'] for d in self.final_results]
                self.final_results = {
                    'rps': sum(rps) / len(rps),
                    'latency': sum(latency) / len(latency),
                    'ecount': sum(ecount) / len(ecount),
                    'epercent': sum(epercent) / len(epercent)
                }

    def write_jmeter_config(self, jconfig, target):
        with open(ORIGINAL_JMETER_FILE, 'r') as f:
            default_jmeter_config = f.read()

        parsed_xml = xmltodict.parse(default_jmeter_config)
        xml_short = parsed_xml['jmeterTestPlan']['hashTree']['hashTree']

        # Change thread number
        xml_short['ThreadGroup']['stringProp'][1]['#text'] = str(jconfig['threads'])
        # Change ramp up time
        xml_short['ThreadGroup']['stringProp'][2]['#text'] = str(jconfig['ramp_up'])
        # Change duration
        xml_short['ThreadGroup']['stringProp'][3]['#text'] = str(jconfig['duration'])
        # Change target
        xml_short['hashTree']['HTTPSamplerProxy']['stringProp'][0]['#text'] = target
        # Change port
        xml_short['hashTree']['HTTPSamplerProxy']['stringProp'][1]['#text'] = str(jconfig['port'])
        # Change path
        xml_short['hashTree']['HTTPSamplerProxy']['stringProp'][6]['#text'] = str(jconfig['path'])

        with open(NEW_JMETER_FILE, 'w') as f:
            f.write(xmltodict.unparse(parsed_xml).encode('utf-8'))


class ConfigError(Exception):

    def __init__(self, message):
        super(ConfigError, self).__init__(message)
        self.message = message
