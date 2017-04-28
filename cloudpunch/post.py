import yaml
import json
import os
import logging

from tabulate import tabulate

SUPPORTED_TESTS = ['fio', 'iperf', 'stress', 'ping', 'jmeter']
SUPPORTED_FORMATS = ['json', 'yaml', 'table', 'csv']


class Post(object):

    def __init__(self, filename, format_type='yaml', output_file=None, raw_mode=False):
        self.filename = filename
        self.format_type = format_type
        self.output_file = output_file
        self.raw_mode = raw_mode

    def run(self):
        # Check if results file exists
        if not os.path.isfile(self.filename):
            raise PostExcept('Cannot find file %s' % self.filename)

        # Check if format type is valid
        if self.format_type not in SUPPORTED_FORMATS:
            raise PostExcept('%s is not a valid format type. Must be json, yaml, table, or csv' % self.format_type)

        # Load results file
        with open(self.filename) as f:
            contents = f.read()
        try:
            data = yaml.load(contents)
        except yaml.YAMLError as e:
            raise PostExcept(e)
        # List of tests inside the results file
        tests = data[0]['results'].keys()

        # Process results into a list
        results = self.create_list(tests, data)

        # Process the list for total, mean, median, mode, range
        results = self.process_results(results)

        # Format the results
        results = self.format_results(results)

        # Print out to a file if output_file is set
        if self.output_file:
            with open(self.output_file, 'w') as f:
                f.write(results)
            logging.info('Saved converted results to %s', self.output_file)
        # Otherwise print to logging
        else:
            logging.info('Converted results:\n%s', results)

    def create_list(self, tests, data):
        results = {}
        for test in tests:
            # Check if test is in the supported list
            if test not in SUPPORTED_TESTS:
                logging.warning('%s is not a supported test', test)
                continue
            # Populate dictionaries with keys
            if test == 'fio':
                sequence = {}
            else:
                sequence = self.populate_dict(test)

            # Go through results data
            for server in data:
                try:
                    if test == 'fio':
                        for jobname in server['results'][test]:
                            if jobname not in sequence:
                                sequence[jobname] = self.populate_dict(test)
                            for io_type in ['read', 'write']:
                                for stat in ['latency_msec', 'iops', 'bandwidth_bytes', 'total_bytes']:
                                    sequence[jobname][io_type][stat].append(server['results'][test][jobname][io_type][stat])
                    elif test == 'iperf':
                        for stat in ['bps', 'retransmits']:
                            sequence[stat].append(server['results'][test][stat])
                    elif test == 'stress':
                        for iteration in server['results']['stress']:
                            for stat in ['cpu', 'timeout', 'load']:
                                sequence[stat].append(iteration[stat])
                    elif test == 'ping':
                        for stat in ['duration', 'latency']:
                            sequence[stat].append(server['results'][test][stat])
                    elif test == 'jmeter':
                        for stat in ['requests_per_second', 'latency_msec', 'error_count', 'error_percent']:
                            sequence[stat].append(server['results'][test][stat])
                except KeyError:
                    raise PostExcept('Server %s has an invalid format for test %s' % (server['hostname'], test))
            results[test] = sequence
        return results

    def populate_dict(self, test):
        # Used to populate the dictionary
        d = {}
        if test == 'fio':
            for label in ['read', 'write']:
                d[label] = {}
                for label2 in ['latency_msec', 'iops', 'bandwidth_bytes', 'total_bytes']:
                    d[label][label2] = []
        elif test == 'iperf':
            for label in ['bps', 'retransmits']:
                d[label] = []
        elif test == 'stress':
            for label in ['cpu', 'timeout', 'load']:
                d[label] = []
        elif test == 'ping':
            for label in ['duration', 'latency']:
                d[label] = []
        elif test == 'jmeter':
            for label in ['requests_per_second', 'latency_msec', 'error_count', 'error_percent']:
                d[label] = []
        else:
            raise PostExcept('Unsupported test type %s' % test)
        return d

    def process_results(self, data):
        results = {}
        for label in ['total', 'mean', 'median', 'mode', 'minrange', 'maxrange']:
            results[label] = {}

        for test in data:
            for label in results:
                results[label][test] = {}
            if test == 'fio':
                for jobname in data[test]:
                    for label in results:
                        results[label][test][jobname] = {}
                    for io_type in data[test][jobname]:
                        for label in results:
                            results[label][test][jobname][io_type] = {}
                        for stat in data[test][jobname][io_type]:
                            stat_data = sorted(data[test][jobname][io_type][stat])
                            results['total'][test][jobname][io_type][stat] = sum(stat_data)
                            results['mean'][test][jobname][io_type][stat] = sum(stat_data) / len(stat_data)
                            results['median'][test][jobname][io_type][stat] = self.median(stat_data)
                            results['mode'][test][jobname][io_type][stat] = max(set(stat_data), key=stat_data.count)
                            results['minrange'][test][jobname][io_type][stat] = stat_data[0]
                            results['maxrange'][test][jobname][io_type][stat] = stat_data[len(stat_data) - 1]
                if not self.raw_mode:
                    for label in results:
                        results[label][test] = self.convert(test, results[label][test])
            else:
                for stat in data[test]:
                    stat_data = sorted(data[test][stat])
                    results['total'][test][stat] = sum(stat_data)
                    results['mean'][test][stat] = sum(stat_data) / len(stat_data)
                    results['median'][test][stat] = self.median(stat_data)
                    results['mode'][test][stat] = max(set(stat_data), key=stat_data.count)
                    results['minrange'][test][stat] = stat_data[0]
                    results['maxrange'][test][stat] = stat_data[len(stat_data) - 1]
                if not self.raw_mode:
                    for label in results:
                        results[label][test] = self.convert(test, results[label][test])

        return results

    def median(self, data):
        if len(data) % 2 == 1:
            return data[((len(data) + 1) / 2) - 1]
        else:
            middle = len(data) / 2
            return float(sum(data[middle - 1:middle + 1])) / 2.0

    def convert(self, test, data):
        # Used to convert raw numbers to human readable
        converted = {}
        if test == 'fio':
            for jobname in data:
                converted[jobname] = {}
                for io_type in ['read', 'write']:
                    converted[jobname][io_type] = {
                        'latency_msec': round(data[jobname][io_type]['latency_msec'], 2),
                        'iops': self.human_format(data[jobname][io_type]['iops']),
                        'bandwidth_bytes': '%sBps' % self.human_format_bytes(data[jobname][io_type]['bandwidth_bytes']),
                        'total_bytes': '%sB' % self.human_format_bytes(data[jobname][io_type]['total_bytes'])
                    }
        elif test == 'iperf':
            converted = {
                'bps': '%sbps' % self.human_format(data['bps']),
                'retransmits': self.human_format(data['retransmits'])
            }
        elif test == 'stress':
            converted = {
                'cpu': round(data['cpu'], 2),
                'timeout': round(data['timeout'], 2),
                'load': round(data['load'], 2)
            }
        elif test == 'ping':
            converted = {
                'duration': round(data['duration'], 2),
                'latency': round(data['latency'], 2)
            }
        elif test == 'jmeter':
            converted = {
                'requests_per_second': round(data['requests_per_second'], 1),
                'latency_msec': data['latency_msec'],
                'error_count': data['error_count'],
                'error_percent': '%s%%' % round(data['error_percent'], 2),
            }
        else:
            raise PostExcept('Unsupported test type %s' % test)
        return converted

    def human_format(self, num):
        if num < 1000:
            return round(num, 2)
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0
        return '%.2f %s' % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])

    def human_format_bytes(self, num):
        if num < 1024:
            return round(num, 2)
        magnitude = 0
        while abs(num) >= 1024:
            magnitude += 1
            num /= 1024.0
        return '%.2f %s' % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])

    def format_results(self, results):
        if self.format_type == 'yaml':
            return yaml.dump(results, default_flow_style=False)
        elif self.format_type == 'json':
            return json.dumps(results)
        elif self.format_type in ['table', 'csv']:
            tables = []
            tests = results['mean'].keys()
            for test in tests:
                table = []
                # fio is special because it has stats for each job
                if test == 'fio':
                    for jobname in results['mean']['fio'].keys():
                        # Create fio job header
                        table.append(['fio %s' % jobname])
                        header = ['stat']
                        for io_type in ['read', 'write']:
                            for stat in ['iops', 'latency_msec', 'bandwidth_bytes', 'total_bytes']:
                                header.append('%s %s' % (io_type, stat))
                        table.append(header)
                        for label in ['mean', 'median', 'mode', 'minrange', 'maxrange', 'total']:
                            # Create fio job row
                            row = [label]
                            for io_type in ['read', 'write']:
                                for stat in ['iops', 'latency_msec', 'bandwidth_bytes', 'total_bytes']:
                                    row.append(results[label]['fio'][jobname][io_type][stat])
                            table.append(row)
                # Create headers
                elif test == 'iperf':
                    table.append(['iperf'])
                    table.append(['stat', 'bps', 'retransmits'])
                elif test == 'stress':
                    table.append(['stress'])
                    table.append(['stat', 'cpu', 'timeout', 'load'])
                elif test == 'ping':
                    table.append(['ping'])
                    table.append(['stat', 'duration', 'latency'])
                elif test == 'jmeter':
                    table.append(['jmeter'])
                    table.append(['stat', 'requests_per_second', 'latency_msec', 'error_count', 'error_percent'])
                for label in ['mean', 'median', 'mode', 'minrange', 'maxrange', 'total']:
                    # Create rows except fio
                    if test == 'iperf':
                        table.append([label,
                                      results[label][test]['bps'],
                                      results[label][test]['retransmits']])
                    elif test == 'stress':
                        table.append([label,
                                      results[label][test]['cpu'],
                                      results[label][test]['timeout'],
                                      results[label][test]['load']])
                    elif test == 'ping':
                        table.append([label,
                                      results[label][test]['duration'],
                                      results[label][test]['latency']])
                    elif test == 'jmeter':
                        table.append([label,
                                      results[label][test]['requests_per_second'],
                                      results[label][test]['latency_msec'],
                                      results[label][test]['error_count'],
                                      results[label][test]['error_percent']])
                tables.append(table)
            current_table = 0
            final_table = ''
            for table in tables:
                current_table += 1
                if self.format_type == 'table':
                    test = table.pop(0)
                    final_table += '~~~~~~~~~~~~~~~ %s ~~~~~~~~~~~~~~~\n' % test[0]
                    final_table += tabulate(table, headers='firstrow', tablefmt='psql')
                elif self.format_type == 'csv':
                    lines = []
                    for row in table:
                        lines.append(','.join(map(str, row)))
                    final_table += '\n'.join(lines)
                if current_table < len(tables):
                    final_table += '\n'
            return final_table


class PostExcept(Exception):

    def __init__(self, message):
        super(PostExcept, self).__init__(message)
        self.message = message
