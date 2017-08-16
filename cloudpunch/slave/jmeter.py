import os
import subprocess
import collections
import xmltodict
import logging
import time

from threading import Thread

SLAVE_PATH = os.path.dirname(os.path.realpath(__file__))
ORIGINAL_JMETER_FILE = '%s/jmeter-test.jmx' % SLAVE_PATH
NEW_JMETER_FILE = '%s/generated-jmeter-test.jmx' % SLAVE_PATH


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = []
        super(CloudPunchTest, self).__init__()

    def run(self):
        try:
            default_config = {
                'jmeter': {
                    'threads': 10,
                    'ramp-up': 0,
                    'duration': 60,
                    'port': 80,
                    'path': '/api/system/health',
                    'gunicorn': {
                        'workers': 5,
                        'threads': 4
                    }
                }
            }
            self.merge_configs(default_config, self.config)
            self.config = default_config
            self.runtest()
        except Exception as e:
            # Send exceptions back to master
            self.final_results = '%s: %s' % (type(e).__name__, e.message)
            logging.error(self.final_results)

    def runtest(self):
        # Start the gunicorn Flask webserver
        if self.config['role'] == 'server' and self.config['server_client_mode']:
            workers = self.config['jmeter']['gunicorn']['workers']
            threads = self.config['jmeter']['gunicorn']['threads']
            logging.info('Starting the gunicorn Flask app with %s workers and %s threads',
                         workers, threads)
            os.popen('gunicorn -D --bind 0.0.0.0:80 --pythonpath %s flaskapp:app -w %s --threads %s' % (SLAVE_PATH,
                                                                                                        workers,
                                                                                                        threads))
            self.final_results = 'ServerMode'

        # Start jmeter
        elif self.config['role'] == 'client' or not self.config['server_client_mode']:
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

            total_time = 0
            for line in iter(popen.stdout.readline, b''):
                line = line.strip()
                if line.count('=') != 2 and not self.config['overtime_results']:
                    continue
                if '+' not in line and self.config['overtime_results']:
                    continue
                line = ' '.join(line.split()).split()
                if self.config['overtime_results']:
                    total_time += int(line[4].split(':')[-1])
                    self.final_results.append({
                        'time': total_time,
                        'requests_per_second': float(line[6][:-2]),
                        'latency_msec': int(line[8]),
                        'error_count': int(line[14]),
                        'error_percent': float(filter(lambda x: x not in '()%', line[15]))
                    })
                else:
                    self.final_results = {
                        'requests_per_second': float(line[6][:-2]),
                        'latency_msec': int(line[8]),
                        'error_count': int(line[14]),
                        'error_percent': float(filter(lambda x: x not in '()%', line[15]))
                    }

            popen.stdout.close()

    def merge_configs(self, default, new):
        for key, value in new.iteritems():
            if (key in default and isinstance(default[key], dict) and
                    isinstance(new[key], collections.Mapping)):
                self.merge_configs(default[key], new[key])
            else:
                default[key] = new[key]

    def write_jmeter_config(self, jconfig, target):
        with open(ORIGINAL_JMETER_FILE, 'r') as f:
            default_jmeter_config = f.read()

        parsed_xml = xmltodict.parse(default_jmeter_config)
        xml_short = parsed_xml['jmeterTestPlan']['hashTree']['hashTree']

        # Change thread number
        xml_short['ThreadGroup']['stringProp'][1]['#text'] = str(jconfig['threads'])
        # Change ramp up time
        xml_short['ThreadGroup']['stringProp'][2]['#text'] = str(jconfig['ramp-up'])
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
