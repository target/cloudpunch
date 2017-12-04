import logging
import subprocess
import json

import cloudpunch.utils.config as cpc
import cloudpunch.utils.metrics as metrics

from threading import Thread

# Complete names are generated during send
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
            # Send exceptions back to control
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
                if jobname not in self.final_results:
                    self.final_results[jobname] = {}
                    for label in ['read', 'write']:
                        self.final_results[jobname][label] = []
                for label in ['read', 'write']:
                    # Job hasn't run yet
                    if job[label]['io_bytes'] == 0:
                        continue
                    # Job has completed
                    if self.final_results[jobname][label]:
                        last_bytes = self.final_results[jobname][label][-1]['bytes'] / 1000
                        if job[label]['io_bytes'] == last_bytes:
                            continue

                    now = data['timestamp']
                    total_bytes = job[label]['io_bytes'] * 1000  # convert from kb to b
                    bandwidth = job[label]['bw'] * 1000  # convert from kbps to bps
                    latency = job[label]['lat']['mean'] / 1000  # convert from micro to milli seconds
                    iops = job[label]['iops']

                    self.final_results[jobname][label].append({
                        'time': now,
                        'bytes': total_bytes,
                        'bandwidth': bandwidth,
                        'latency': latency,
                        'iops': iops
                    })
                    if self.config['metrics']['enable']:
                        extra_tags = {'job': jobname}
                        self.metric.send_metric('%s.%s.bytes' % (METRIC_NAME, label), total_bytes, now, extra_tags)
                        self.metric.send_metric('%s.%s.bandwidth' % (METRIC_NAME, label), bandwidth, now, extra_tags)
                        self.metric.send_metric('%s.%s.latency' % (METRIC_NAME, label), latency, now, extra_tags)
                        self.metric.send_metric('%s.%s.iops' % (METRIC_NAME, label), iops, now, extra_tags)

        popen.stdout.close()

        # Send back summary if not over time
        if not self.config['overtime_results']:
            for jobname in results:
                for label in ['read', 'write']:
                    total_bytes = [d['bytes'] for d in self.final_results[jobname][label]]
                    bandwidth = [d['bandwidth'] for d in self.final_results[jobname][label]]
                    latency = [d['latency'] for d in self.final_results[jobname][label]]
                    iops = [d['iops'] for d in self.final_results[jobname][label]]
                    try:
                        # Exception will happen if results were 0 (possibly because a 0% read/write)
                        self.final_results[jobname][label] = {
                            'bytes': total_bytes[-1],
                            'bandwidth': sum(bandwidth) / len(bandwidth),
                            'latency': sum(latency) / len(latency),
                            'iops': sum(iops) / len(iops)
                        }
                    except ZeroDivisionError:
                        self.final_results[jobname][label] = {
                            'bytes': 0,
                            'bandwidth': 0,
                            'latency': 0,
                            'iops': 0
                        }
