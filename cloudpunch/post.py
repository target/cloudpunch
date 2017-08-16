import yaml
import json
import os
import logging
import plotly
import plotly.graph_objs as go

from tabulate import tabulate

SUPPORTED_TESTS = ['fio', 'iperf', 'stress', 'ping', 'jmeter']
SUPPORTED_FORMATS = ['json', 'yaml', 'table', 'csv', 'graph']

GRAPH_LABELS = {
    'time': 'Seconds',
    'iops': 'Input/Output Operations per Second (IOPS)',
    'latency': 'Latency (msec)',
    'bandwidth': 'Bandwidth (Bps)',
    'bytes': 'Total Bytes',
    'bps': 'Throughput (Gbps)',
    'retransmits': 'Retransmits',
    'load': 'CPU Load',
    'cpu': 'CPU Count',
    'requests': 'Requests per Second',
    'ecount': 'Error Count',
    'epercent': 'Error Percent'
}
GRAPH_MAPPINGS = {
    'fio': {
        'iops': 'iops',
        'latency': 'latency_msec',
        'bandwidth': 'bandwidth_bytes',
        'bytes': 'total_bytes'
    },
    'iperf': {
        'bps': 'bps',
        'retransmits': 'retransmits'
    },
    'stress': {
        'load': 'load',
        'cpu': 'cpu'
    },
    'ping': {
        'latency': 'latency'
    },
    'jmeter': {
        'requests': 'requests_per_second',
        'ecount': 'error_count',
        'epercent': 'error_percent',
        'latency': 'latency_msec'
    }
}
GRAPH_DEFAULTS = {
    'fio': 'iops',
    'iperf': 'bps',
    'stress': 'load',
    'ping': 'latency',
    'jmeter': 'requests'
}


class Post(object):

    def __init__(self, filename, format_type='yaml', output_file=None, stat=None, test=None,
                 fiojob=None, summary=False, raw_mode=False, open_graph=False):
        self.filename = filename
        self.format_type = format_type
        self.output_file = output_file
        self.stat = stat
        self.test = test
        self.fiojob = fiojob
        self.summary = summary
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

        # Check if supplied test is in results
        if self.test and self.test not in tests:
            raise PostExcept('Results does not contain test %s, it contains: %s' % (self.test,
                                                                                    ', '.join(tests)))

        # Check if this data is a summary or over time
        for test in tests:
            if test == 'fio':
                fio_test = data[0]['results'][test].keys()[0]
                if isinstance(data[0]['results'][test][fio_test]['read'], list):
                    self.overtime = True
            elif isinstance(data[0]['results'][test], list):
                self.overtime = True
            elif self.overtime:
                raise PostExcept('Results are a mix of summary and over time, only one is allowed')

        # Process results into a list
        results = self.create_list(tests, data)

        if self.overtime and self.summary:
            self.overtime = False
            results = self.summarize_results(results)

        # Process the list for total, mean, median, mode, range
        if not self.overtime:
            results = self.process_results(results)

        # Format the results
        results = self.format_results(results)

        # format_results handles the rest for graph
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
                    if self.overtime:
                        if server['hostname'] not in sequence:
                            sequence[server['hostname']] = {}
                        for jobname in server['results'][test]:
                            if jobname not in sequence:
                                sequence[server['hostname']][jobname] = {}
                            for io_type in server['results'][test][jobname]:
                                if io_type not in sequence[server['hostname']][jobname]:
                                    sequence[server['hostname']][jobname][io_type] = {}
                                for time in server['results'][test][jobname][io_type]:
                                    for stat in time:
                                        if stat not in sequence[server['hostname']][jobname][io_type]:
                                            sequence[server['hostname']][jobname][io_type][stat] = []
                                        sequence[server['hostname']][jobname][io_type][stat].append(time[stat])
                    else:
                        for jobname in server['results'][test]:
                            if jobname not in sequence:
                                sequence[jobname] = {}
                            for io_type in server['results'][test][jobname]:
                                if io_type not in sequence[jobname]:
                                    sequence[jobname][io_type] = {}
                                for stat in server['results'][test][jobname][io_type]:
                                    if stat not in sequence[jobname][io_type]:
                                        sequence[jobname][io_type][stat] = []
                                    if self.overtime:
                                        for result in server['results'][test][jobname][io_type][stat]:
                                            sequence[jobname][io_type][stat].append(result[stat])
                                    else:
                                        num = server['results'][test][jobname][io_type][stat]
                                        sequence[jobname][io_type][stat].append(num)
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

    def summarize_results(self, data):
        results = {}
        for test in data:
            if test not in results:
                results[test] = {}
            for server in data[test]:
                if test == 'fio':
                    for jobname in data[test][server]:
                        if jobname not in results[test]:
                            results[test][jobname] = {}
                        for io_type in data[test][server][jobname]:
                            if io_type not in results[test][jobname]:
                                results[test][jobname][io_type] = {}
                            for stat in data[test][server][jobname][io_type]:
                                if stat == 'time':
                                    continue
                                if stat not in results[test][jobname][io_type]:
                                    results[test][jobname][io_type][stat] = []
                                current_data = data[test][server][jobname][io_type][stat]
                                summarized = sum(current_data) / len(current_data)
                                results[test][jobname][io_type][stat].append(summarized)
                else:
                    for stat in data[test][server]:
                        if stat == 'time':
                            continue
                        if stat not in results[test]:
                            results[test][stat] = []
                        summarized = sum(data[test][server][stat]) / len(data[test][server][stat])
                        results[test][stat].append(summarized)
        return results

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
                if not self.raw_mode and self.format_type != 'graph':
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
                if not self.raw_mode and self.format_type != 'graph':
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
            if self.overtime:
                raise PostExcept('Table and CSV formats do not support over time results')
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
            if not self.overtime:
                raise PostExcept('Graph format does not support summary results')
            for test in results:
                if self.test and test != self.test:
                    continue
                traces = []
                for server in results[test]:
                    x = []
                    y = []
                    if test == 'fio':
                        x2 = []
                        y2 = []
                        fio_tests = results[test][server].keys()
                        if len(fio_tests) == 1:
                            process_test = fio_tests[0]
                            if self.fiojob and process_test != self.fiojob:
                                logging.warning('Results has only one fio job %s, ignoring given test %s',
                                                process_test, self.fiojob)
                        elif self.fiojob:
                            if self.fiojob not in fio_tests:
                                valid_options = ', '.join(fio_tests)
                                raise PostExcept('Results do not have fio job %s, must be: %s' % (self.fiojob,
                                                                                                  valid_options))
                            process_test = self.fiojob
                        else:
                            valid_options = ', '.join(fio_tests)
                            raise PostExcept('Results have multiple fio jobs (%s), supply one with -t' % valid_options)
                        for io_type in ['read', 'write']:
                            # process x axis
                            for time in results[test][server][process_test][io_type]['time']:
                                current_time = time - results[test][server][process_test][io_type]['time'][0] + 1
                                if io_type == 'read':
                                    x.append(current_time)
                                else:
                                    x2.append(current_time)
                            # validate test stat
                            if not self.stat:
                                self.stat = GRAPH_DEFAULTS[test]
                            if self.stat not in GRAPH_MAPPINGS[test]:
                                valid_options = ', '.join(GRAPH_MAPPINGS[test].keys())
                                raise PostExcept('%s does not have the stat %s to graph, must be: %s' % (test,
                                                                                                         self.stat,
                                                                                                         valid_options))
                            # process y axis
                            current_seq = results[test][server][process_test][io_type][GRAPH_MAPPINGS[test][self.stat]]
                            if io_type == 'read':
                                y = current_seq
                            else:
                                y2 = current_seq
                    else:
                        # process x axis
                        if test == 'stress':
                            current_time = 0
                            for time in results[test][server]['timeout']:
                                x.append(current_time)
                                current_time += time
                                x.append(current_time)
                        elif test in ['ping', 'iperf']:
                            for time in results[test][server]['time']:
                                x.append(round(time - results[test][server]['time'][0] + 1))
                        elif test == 'jmeter':
                            x = results[test][server]['time']
                        # validate test stat
                        if not self.stat:
                            self.stat = GRAPH_DEFAULTS[test]
                        if self.stat not in GRAPH_MAPPINGS[test]:
                            valid_options = ', '.join(GRAPH_MAPPINGS[test].keys())
                            raise PostExcept('%s does not have the stat %s to graph, must be: %s' % (test,
                                                                                                     self.stat,
                                                                                                     valid_options))
                        # process y axis
                        if test == 'stress':
                            for value in results[test][server][self.stat]:
                                y += [value] * 2
                        elif test == 'iperf' and self.stat == 'bps':
                            for bit in results[test][server][self.stat]:
                                y.append(bit / 1000000000)
                        else:
                            y = results[test][server][GRAPH_MAPPINGS[test][self.stat]]
                    if test == 'fio':
                        traces.append(go.Scatter(x=x,
                                                 y=y,
                                                 mode='lines+markers',
                                                 name='%s-%s' % ('read', '-'.join(server.split('-')[3:]))))
                        traces.append(go.Scatter(x=x2,
                                                 y=y2,
                                                 mode='lines+markers',
                                                 name='%s-%s' % ('write', '-'.join(server.split('-')[3:]))))
                    else:
                        traces.append(go.Scatter(x=x,
                                                 y=y,
                                                 mode='lines+markers',
                                                 name='-'.join(server.split('-')[3:])))
                layout = go.Layout(title='CloudPunch %s %s' % (test, self.stat),
                                   xaxis={'title': GRAPH_LABELS['time']},
                                   yaxis={'title': GRAPH_LABELS[self.stat]})
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
