import yaml
import os
import logging
import argparse


LOGFORMAT = '%(asctime)-15s %(levelname)s %(message)s'
DATEFORMAT = '%Y-%m-%d %H:%M:%S'
__version__ = '1.2.0'

SUPPORTED_TESTS = ['fio', 'iperf', 'stress', 'ping']


class PostExcept(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(prog='cloudpunch-post',
                                     description='Process data from CloudPunch',
                                     version=__version__)
    parser.add_argument('-f',
                        '--file',
                        action='store',
                        dest='results_file',
                        default=None,
                        help='results file from CloudPunch')
    parser.add_argument('-o',
                        '--output',
                        action='store',
                        dest='output_file',
                        default=None,
                        help='file to save processed results to (default: stdout)')
    parser.add_argument('--raw',
                        action='store_true',
                        dest='raw_mode',
                        help='converted results are raw numbers')
    parser.add_argument('-l',
                        '--loglevel',
                        action='store',
                        dest='log_level',
                        default='INFO',
                        help='log level (default: INFO)')
    parser.add_argument('-L',
                        '--logfile',
                        action='store',
                        dest='log_file',
                        default=None,
                        help='file to log to (default: stdout)')

    args = parser.parse_args()

    # Get logging level int from string
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        print 'Invalid log level %s, using default of INFO' % args.log_level
        numeric_level = getattr(logging, 'INFO', None)
    logging.basicConfig(format=LOGFORMAT,
                        datefmt=DATEFORMAT,
                        level=numeric_level,
                        filename=args.log_file)

    # Results file is required
    if not args.results_file:
        raise PostExcept('Missing CloudPunch results file')
    filename = args.results_file
    # Check if results file exists
    if not os.path.isfile(filename):
        raise PostExcept('Cannot find file %s' % filename)

    # Load results file
    data = loadfile(filename)
    results = {}
    # List of tests inside the results file
    tests = data[0]['results'].keys()

    for test in tests:
        # Check if test is in the support list
        if test not in SUPPORTED_TESTS:
            logging.warning('%s is not a supported test', test)
            continue
        # Populate dictionaries with keys
        if test == 'fio':
            totals = {}
            averages = {}
        else:
            totals = populate_dict(test)
            averages = populate_dict(test)
        count = len(data)
        # Go through results data
        for server in data:
            try:
                if test == 'fio':
                    for jobname in server['results']['fio']:
                        if jobname not in totals:
                            totals[jobname] = populate_dict(test)
                        if jobname not in averages:
                            averages[jobname] = populate_dict(test)
                        for label in ['read', 'write']:
                            for label2 in ['latency_msec', 'iops', 'bandwidth_bytes', 'total_bytes']:
                                totals[jobname][label][label2] += server['results']['fio'][jobname][label][label2]
                                averages[jobname][label][label2] = totals[jobname][label][label2] / count
                elif test == 'iperf':
                    for label in ['bps', 'retransmits']:
                        totals[label] += server['results']['iperf'][label]
                        averages[label] = totals[label] / count
                elif test == 'stress':
                    for iteration in server['results']['stress']:
                        for label in ['cpu', 'timeout', 'load']:
                            totals[label] += iteration[label]
                            averages[label] = totals[label] / count
                elif test == 'ping':
                    for label in ['duration', 'latency']:
                        totals[label] += server['results']['ping'][label]
                        averages[label] = totals[label] / count
            except KeyError:
                raise PostExcept('Server %s has an invalid format for test %s' % (server['hostname'], test))
        # Convert results to human readable if raw mode is not enabled
        results[test] = {
            'totals': convert(test, totals) if not args.raw_mode else totals,
            'averages': convert(test, averages) if not args.raw_mode else averages
        }
    # Print out to a file if output_file is set
    if args.output_file:
        ofile = open(args.output_file, 'w')
        ofile.write(yaml.dump(results, default_flow_style=False))
        ofile.close()
        logging.info('Saved converted results to %s', args.output_file)
    # Otherwise print to logging
    else:
        logging.info('Converted results:\n%s', yaml.dump(results, default_flow_style=False))


def populate_dict(test):
    # Used to populate the dictionary
    d = {}
    if test == 'fio':
        for label in ['read', 'write']:
            d[label] = {}
            for label2 in ['latency_msec', 'iops', 'bandwidth_bytes', 'total_bytes']:
                d[label][label2] = 0
    elif test == 'iperf':
        for label in ['bps', 'retransmits']:
            d[label] = 0
    elif test == 'stress':
        for label in ['cpu', 'timeout', 'load']:
            d[label] = 0
    elif test == 'ping':
        for label in ['duration', 'latency']:
            d[label] = 0
    else:
        raise PostExcept('Unsupported test type %s' % test)
    return d


def convert(test, data):
    # Used to convert raw numbers to human readable
    converted = {}
    if test == 'fio':
        for jobname in data:
            converted[jobname] = {}
            for label in ['read', 'write']:
                converted[jobname][label] = {
                    'latency_msec': round(data[jobname][label]['latency_msec'], 2),
                    'iops': human_format(data[jobname][label]['iops']),
                    'bandwidth_bytes': '%sBps' % human_format_bytes(data[jobname][label]['bandwidth_bytes']),
                    'total_bytes': '%sB' % human_format_bytes(data[jobname][label]['total_bytes'])
                }
    elif test == 'iperf':
        converted = {
            'bps': '%sbps' % human_format(data['bps']),
            'retransmits': human_format(data['retransmits'])
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
    else:
        raise PostExcept('Unsupported test type %s' % test)
    return converted


def loadfile(filename):
    contents = open(filename).read()
    try:
        data = yaml.load(contents)
    except yaml.YAMLError as e:
        raise PostExcept(e)
    return data


def human_format(num):
    if num < 1000:
        return round(num, 2)
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '%.2f %s' % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])


def human_format_bytes(num):
    if num < 1024:
        return round(num, 2)
    magnitude = 0
    while abs(num) >= 1024:
        magnitude += 1
        num /= 1024.0
    return '%.2f %s' % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])


if __name__ == '__main__':
    try:
        main()
    except PostExcept as e:
        logging.error(e.message)
