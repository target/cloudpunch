import logging
import subprocess
import json

import cloudpunch.utils.config as cpc
import cloudpunch.utils.metrics as metrics

from threading import Thread

METRIC_NAME = 'cloudpunch.fio'


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = {}
        if self.config['metrics']['enable']:
            self.metric = metrics.Metrics(self.config['metrics'])
        super(CloudPunchTest, self).__init__()

    def run(self):
        try:
            default_config = {
                'fio': {
                    'randrepeat': 1,
                    'ioengine': 'libaio',
                    'direct': 1,
                    'filename': '/fiotest',
                    'bsrange': '4k-8k',
                    'iodepth': 8,
                    'size': '1G',
                    'readwrite': 'randrw',
                    'rwmixread': 50,
                    'numjobs': 1,
                    'status-interval': 1,
                    'runtime': 300
                }
            }
            self.config = cpc.merge_configs(default_config, self.config)
            self.runtest()
        except Exception as e:
            # Send exceptions back to master
            logging.error('%s: %s', type(e).__name__, e.message)
            self.final_results = '%s: %s' % (type(e).__name__, e.message)

    def runtest(self):
        # Create command
        if 'test_file_data' in self.config['fio']:
            with open('/tmp/job.fio', 'w') as f:
                f.write(self.config['fio']['test_file_data'])
            fio_command = ('fio --output-format=json --status-interval=%s '
                           '/tmp/job.fio | jq -c .') % self.config['fio']['status-interval']
        else:
            fio_command = 'fio --name=fiotest --time_based --output-format=json'
            for key in self.config['fio']:
                fio_command += ' --%s=%s' % (key, self.config['fio'][key])
            fio_command += ' | jq -c .'

        # Run the fio command while iterating through stdout
        logging.info('Running fio command: %s', fio_command)
        popen = subprocess.Popen(fio_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

        results = {}

        for line in iter(popen.stdout.readline, b''):
            line = line.rstrip()
            data = json.loads(line)
            for job in data['jobs']:
                jobname = job['jobname']
                if not self.config['overtime_results']:
                    if jobname not in results:
                        # Setup default dictionary for each job
                        results[jobname] = {}
                        for label in ['read', 'write']:
                            results[jobname][label] = {}
                            for label2 in ['bytes', 'bw', 'lat', 'iops']:
                                results[jobname][label][label2] = []
                    for label in ['read', 'write']:
                        # Job hasn't run yet
                        if job[label]['io_bytes'] == 0:
                            continue
                        # Job has completed
                        if job[label]['io_bytes'] == results[jobname][label]['bytes']:
                            continue
                        results[jobname][label]['bytes'] = job[label]['io_bytes'] * 1000
                        results[jobname][label]['bw'].append(job[label]['bw'] * 1000)
                        results[jobname][label]['lat'].append(job[label]['lat']['mean'] / 1000)
                        results[jobname][label]['iops'].append(job[label]['iops'])
                else:
                    if jobname not in self.final_results:
                        self.final_results[jobname] = {}
                        for label in ['read', 'write']:
                            self.final_results[jobname][label] = []
                    for label in ['read', 'write']:
                        self.final_results[jobname][label].append({
                            'time': data['timestamp'],
                            'bytes': job[label]['io_bytes'] * 1000,
                            'bandwidth': job[label]['bw'] * 1000,
                            'latency': job[label]['lat']['mean'] / 1000,
                            'iops': job[label]['iops']
                        })

        popen.stdout.close()

        if not self.config['overtime_results']:
            for jobname in results:
                self.final_results[jobname] = {}
                for label in ['read', 'write']:
                    try:
                        # Exception will happen if results were 0 (possibly because a 0% read/write)
                        self.final_results[jobname][label] = {
                            'bytes': results[jobname][label]['bytes'],
                            'bandwidth': sum(results[jobname][label]['bw']) / len(results[jobname][label]['bw']),
                            'latency': sum(results[jobname][label]['lat']) / len(results[jobname][label]['lat']),
                            'iops': sum(results[jobname][label]['iops']) / len(results[jobname][label]['iops'])
                        }
                    except ZeroDivisionError:
                        self.final_results[jobname][label] = {
                            'bytes': 0,
                            'bandwidth': 0,
                            'latency': 0,
                            'iops': 0
                        }
