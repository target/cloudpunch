import logging
import subprocess
import collections
import json

from threading import Thread


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = {}
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
            self.merge_configs(default_config, self.config)
            self.config = default_config
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
                        for label in ['read', 'write']:
                            self.final_results[jobname][label] = []
                    for label in ['read', 'write']:
                        self.final_results[jobname][label].append({
                            'time': data['timestamp'],
                            'total_bytes': job[label]['io_bytes'] * 1000,
                            'bandwidth_bytes': job[label]['bw'] * 1000,
                            'latency_msec': job[label]['lat']['mean'] / 1000,
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
                            'total_bytes': results[jobname][label]['bytes'],
                            'bandwidth_bytes': sum(results[jobname][label]['bw']) / len(results[jobname][label]['bw']),
                            'latency_msec': sum(results[jobname][label]['lat']) / len(results[jobname][label]['lat']),
                            'iops': sum(results[jobname][label]['iops']) / len(results[jobname][label]['iops'])
                        }
                    except ZeroDivisionError:
                        self.final_results[jobname][label] = {
                            'total_bytes': 0,
                            'bandwidth_bytes': 0,
                            'latency_msec': 0,
                            'iops': 0
                        }

    def merge_configs(self, default, new):
        for key, value in new.iteritems():
            if (key in default and isinstance(default[key], dict) and
                    isinstance(new[key], collections.Mapping)):
                self.merge_configs(default[key], new[key])
            else:
                default[key] = new[key]
