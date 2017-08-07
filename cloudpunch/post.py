import yaml
import json
import os
import logging
import plotly
import plotly.graph_objs as go

from tabulate import tabulate

SUPPORTED_TESTS = ['fio', 'iperf', 'stress', 'ping', 'jmeter']
SUPPORTED_FORMATS = ['json', 'yaml', 'table', 'csv', 'graph']


class Post(object):

    def __init__(self, filename, format_type='yaml', output_file=None,
                 raw_mode=False, open_graph=False):
        self.filename = filename
        self.format_type = format_type
        self.output_file = output_file
        self.raw_mode = raw_mode
        self.open_graph = open_graph
        self.overtime = False

    def run(self):
        # Check if results file exists
        if not os.path.isfile(self.filename):
            raise PostExcept('Cannot find file %s' % self.filename)

        # Check if format type is valid
        if self.format_type not in SUPPORTED_FORMATS:
            raise PostExcept('%s is not a valid format type. Must be %s' % (self.format_type,
                                                                            ', '.join(SUPPORTED_FORMATS)))

        # Load results file
        with open(self.filename) as f:
            contents = f.read()
        try:
            data = yaml.load(contents)
        except yaml.YAMLError as e:
            raise PostExcept(e)

        # List of tests inside the results file
        tests = data[0]['results'].keys()

        # Check if this data is a summary or over time
        for test in tests:
            if isinstance(data[0]['results'][test], list):
                self.overtime = True
            elif self.overtime:
                raise PostExcept('Results are a mix of summary and over time, only one is allowed')

        # Process results into a list
        results = self.create_list(tests, data)

        # Process the list for total, mean, median, mode, range
        if not self.overtime:
            results = self.process_results(results)

        # Format the results
        results = self.format_results(results)

        if self.format_type == 'graph':
            return
        # Print out to a file if output_file is set
        elif self.output_file:
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

            # Go through results data
            results[test] = self.create_sequence(test, data)
        return results

    def create_sequence(self, test, data):
        sequence = {}
        try:
            for server in data:
                if test == 'fio':
                    for jobname in server['results'][test]:
                        if jobname not in sequence:
                            sequence[jobname] = {}
                        for io_type in server['results'][test][jobname]:
                            for stat in server['results'][test][jobname][io_type]:
                                if stat not in sequence[jobname][io_type]:
                                    sequence[jobname][io_type][stat] = []
                                if self.overtime:
                                    for result in server['results'][test][jobname][io_type][stat]:
                                        sequence[jobname][io_type][stat].append(result[stat])
                                else:
                                    sequence[jobname][io_type][stat].append(server['results'][test][jobname][io_type][stat])
                elif self.overtime:
                    if server['hostname'] not in sequence:
                        sequence[server['hostname']] = {}
                    for time in server['results'][test]:
                        for stat in time:
                            if stat not in sequence[server['hostname']]:
                                sequence[server['hostname']][stat] = []
                            sequence[server['hostname']][stat].append(time[stat])
                else:
                    for stat in server['results'][test]:
                        if stat not in sequence:
                            sequence[stat] = []
                        sequence[stat].append(server['results'][test][stat])
        except KeyError:
            raise PostExcept('Server %s has an invalid format for test %s' % (server['hostname'], test))
        return sequence

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
                        'bandwidth_bytes': '%sBps' % self.human_format(data[jobname][io_type]['bandwidth_bytes']),
                        'total_bytes': '%sB' % self.human_format(data[jobname][io_type]['total_bytes'])
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
        elif self.format_type == 'graph':
            plot_schema = {'data': [], 'label': ''}
            for test in results:
                traces = []
                for server in results[test]:
                    x = plot_schema.copy()
                    y = plot_schema.copy()
                    if test == 'fio':
                        pass
                    elif test == 'iperf':
                        for time in results[test][server]['time']:
                            x['data'].append(time - results[test][server]['time'][0] + 1)
                        x['label'] = 'Seconds'
                        for bit in results[test][server]['bps']:
                            y['data'].append(bit / 1000000000)
                        y['label'] = 'Throughput (Gbps)'
                    elif test == 'stress':
                        pass
                    elif test == 'ping':
                        for time in results[test][server]['time']:
                            x['data'].append(round(time - results[test][server]['time'][0] + 1))
                        x['label'] = 'Seconds'
                        y['data'] = results[test][server]['latency']
                        y['label'] = 'Latency (msec)'
                    elif test == 'jmeter':
                        pass
                    traces.append(go.Scatter(x=x['data'],
                                             y=y['data'],
                                             mode='lines+markers',
                                             name=server))
                layout = go.Layout(title='CloudPunch %s test' % test,
                                   xaxis={'title': x['label']},
                                   yaxis={'title': y['label']})
                fig = go.Figure(data=traces, layout=layout)
                filename = self.output_file
                if not self.output_file:
                    filename = 'cloudpunch-%s-%s.html' % (server.split('-')[1], test)
                plotly.offline.plot(fig, filename=filename, auto_open=self.open_graph)
                logging.info('Created HTML graph file %s', filename)


class PostExcept(Exception):

    def __init__(self, message):
        super(PostExcept, self).__init__(message)
        self.message = message
