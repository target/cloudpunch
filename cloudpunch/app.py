import logging
import argparse
import os

import threading

import cloudpunch.ostlib.exceptions
from cloudpunch import accelerator
from cloudpunch import cleanup
from cloudpunch import configuration
from cloudpunch import environment
from cloudpunch import post
from cloudpunch.ostlib import credentials
from cloudpunch.control import cp_control
from cloudpunch.worker import cp_worker
from cloudpunch.utils import network
from cloudpunch.utils import exceptions


LOGFORMAT = '%(asctime)-15s %(levelname)s %(message)s'
DATEFORMAT = '%Y-%m-%d %H:%M:%S'
__version__ = open(os.path.dirname(os.path.realpath(__file__)) + '/version').read()


def cp_app():
    # Main argument parser
    parser = argparse.ArgumentParser(prog='cloudpunch',
                                     description='Framework for OpenStack performance testing')
    parser.add_argument('-v',
                        '--version',
                        action='version',
                        version=__version__)
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

    subparsers = parser.add_subparsers(dest='workload',
                                       help='workloads')
    # Run parser
    run_parser = subparsers.add_parser('run',
                                       help='run a test')
    run_parser.add_argument('-c',
                            '--config',
                            action='store',
                            dest='config_file',
                            default=None,
                            help='override default configuration with a config file')
    run_parser.add_argument('-e',
                            '--env',
                            action='store',
                            dest='env_file',
                            default=None,
                            help='override default environment with an environment file')
    run_parser.add_argument('-e2',
                            '--env2',
                            action='store',
                            dest='env2_file',
                            default=None,
                            help='environment file for second OpenStack environment')
    run_parser.add_argument('-r',
                            '--openrc',
                            action='store',
                            dest='openrc_file',
                            default=None,
                            help='OpenRC file containing auth info (default: env)')
    run_parser.add_argument('-r2',
                            '--openrc2',
                            action='store',
                            dest='openrc2_file',
                            default=None,
                            help='OpenRC file for second OpenStack environment')
    run_parser.add_argument('-m',
                            '--hostmap',
                            action='store',
                            dest='hostmap_file',
                            default=None,
                            help='file containg a hostmap to control instance location')
    run_parser.add_argument('-b',
                            '--flavor',
                            action='store',
                            dest='flavor_file',
                            default=None,
                            help='file containing a flavor breakdown')
    run_parser.add_argument('-o',
                            '--output',
                            action='store',
                            dest='output_file',
                            default=None,
                            help='file to save results to (default: stdout)')
    run_parser.add_argument('-f',
                            '--format',
                            action='store',
                            dest='format',
                            default='yaml',
                            help='format to save results as (yaml or json)')
    run_parser.add_argument('-p',
                            '--password',
                            action='store',
                            dest='password',
                            default=None,
                            help='password or token to login')
    run_parser.add_argument('-p2',
                            '--password2',
                            action='store',
                            dest='password2',
                            default=None,
                            help='password to login into second OpenStack environment')
    run_parser.add_argument('-i',
                            '--reuse',
                            action='store',
                            dest='cloudpunch_id',
                            default=None,
                            help='CloudPunch ID to connect to')
    run_parser.add_argument('-l',
                            '--listen',
                            action='store',
                            dest='host',
                            default='0.0.0.0',
                            help='host address to listen on (default: 0.0.0.0)')
    run_parser.add_argument('-t',
                            '--port',
                            action='store',
                            dest='port',
                            default='9985',
                            help='port to listen on (default: 9985)')
    run_parser.add_argument('-w',
                            '--connect',
                            action='store',
                            dest='connection',
                            default=None,
                            help='interface or ip address workers connect to')
    run_parser.add_argument('--no-env',
                            action='store_true',
                            dest='no_env',
                            help='do not use environment for authentication')
    run_parser.add_argument('--manual',
                            action='store_true',
                            dest='manual_mode',
                            help='enable manual test start (requires interactive)')
    run_parser.add_argument('--insecure',
                            action='store_false',
                            dest='verify',
                            help='ignore SSL failures')
    # Cleanup parser
    cleanup_parser = subparsers.add_parser('cleanup',
                                           help='cleanup resources')
    cleanup_parser.add_argument('cleanup_file',
                                help='cleanup file containing resource ids, can be search to find resources')
    cleanup_parser.add_argument('-r',
                                '--openrc',
                                action='store',
                                dest='openrc_file',
                                default=None,
                                help='OpenRC file containing auth info (default: env)')
    cleanup_parser.add_argument('-p',
                                '--password',
                                action='store',
                                dest='password',
                                default=None,
                                help='password or token to login')
    cleanup_parser.add_argument('-n',
                                '--dry-run',
                                action='store_true',
                                dest='dry_run',
                                help='do not delete resources')
    cleanup_parser.add_argument('-a',
                                '--names',
                                action='store_true',
                                dest='names',
                                help='display resources found')
    cleanup_parser.add_argument('--no-env',
                                action='store_true',
                                dest='no_env',
                                help='do not use environment for authentication')
    cleanup_parser.add_argument('--insecure',
                                action='store_false',
                                dest='verify',
                                help='ignore SSL failures')
    # Post parser
    post_parser = subparsers.add_parser('post',
                                        help='process results')
    post_parser.add_argument('results_file',
                             help='results file from a test run')
    post_parser.add_argument('-f',
                             '--format',
                             action='store',
                             dest='format',
                             default='yaml',
                             help='convert results to format (json, yaml, table, csv, graph)')
    post_parser.add_argument('-o',
                             '--output',
                             action='store',
                             dest='output_file',
                             default=None,
                             help='file to save processed results to (default: stdout)')
    post_parser.add_argument('-s',
                             '--stat',
                             action='store',
                             dest='stat',
                             default=None,
                             help='stat from test to graph (graph format only)')
    post_parser.add_argument('-t',
                             '--test',
                             action='store',
                             dest='test',
                             default=None,
                             help='test to graph (graph format only)')
    post_parser.add_argument('-j',
                             '--job',
                             action='store',
                             dest='fiojob',
                             default=None,
                             help='fio job to graph (fio test and graph format only)')
    post_parser.add_argument('--summary',
                             action='store_true',
                             dest='summary',
                             help='convert over time results to summary results')
    post_parser.add_argument('--raw',
                             action='store_true',
                             dest='raw_mode',
                             help='converted results are raw numbers (all except graph format)')
    post_parser.add_argument('--open',
                             action='store_true',
                             dest='open_graph',
                             help='open generated graph after creation (graph format only)')

    # Worker parser
    worker_parser = subparsers.add_parser('worker',
                                          help='start a worker server')
    worker_parser.add_argument('control_ip',
                               help='control ip address')
    worker_parser.add_argument('-p',
                               '--port',
                               action='store',
                               dest='control_port',
                               default='9985',
                               help='port to connect to (default: 9985)')

    args = parser.parse_args()

    # Get logging level int from string
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = getattr(logging, 'INFO', None)
        print('Invalid log level %s, using default of INFO' % args.log_level)
    logging.basicConfig(format=LOGFORMAT,
                        datefmt=DATEFORMAT,
                        level=numeric_level,
                        filename=args.log_file)

    # Turn off unwanted info messages
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('kafka').setLevel(logging.ERROR)

    # Run workload
    if args.workload == 'run':

        # Figure out what ip address workers will connect to
        control_ip = network.find_ip_address(args.connection)

        # Start the control server
        logging.info('Starting control server listening on %s:%s', args.host, args.port)
        ct = threading.Thread(name='controlthread', target=controlThread, args=[args.host, args.port])
        ct.daemon = True
        ct.start()

        # Verify results file format
        if args.format not in ['yaml', 'json']:
            raise exceptions.CPError('Invalid format of results file. Must be yaml or json')

        # Split mode means there is two sets of environment and authentication
        env2 = None
        split_mode = False
        # Split mode is enabled if there is a second OpenRC file
        if args.openrc2_file:
            split_mode = True
            # If there is no second environment file, set it to the same as the first
            if not args.env2_file:
                env2 = environment.Environment(args.env_file).get_config()
            else:
                env2 = environment.Environment(args.env2_file).get_config()

        # Create environment dictionary with both env1 and env2
        env = {
            'env1': environment.Environment(args.env_file).get_config(),
            'env2': env2
        }

        # Load in configuration
        config = configuration.Configuration(config_file=args.config_file,
                                             output_file=args.output_file,
                                             hostmap_file=args.hostmap_file,
                                             flavor_file=args.flavor_file,
                                             split_mode=split_mode)

        # Create authentication dictionary with both env1 and env2
        creds_env2 = None
        if split_mode:
            creds_env2 = credentials.Credentials(openrc_file=args.openrc2_file,
                                                 password=args.password2,
                                                 no_env=True,
                                                 interactive=True)
        creds = {
            'env1': credentials.Credentials(openrc_file=args.openrc_file,
                                            password=args.password,
                                            no_env=args.no_env,
                                            interactive=True),
            'env2': creds_env2
        }

        # Create accelerator object and run it
        acc = accelerator.Accelerator(config, creds, env,
                                      control_ip=control_ip,
                                      control_port=args.port,
                                      control_local=args.host,
                                      manual_mode=args.manual_mode,
                                      cloudpunch_id=args.cloudpunch_id,
                                      results_format=args.format,
                                      verify=args.verify)
        acc.run()

    # Cleanup workload
    elif args.workload == 'cleanup':
        creds = credentials.Credentials(openrc_file=args.openrc_file,
                                        password=args.password,
                                        no_env=args.no_env,
                                        interactive=True)
        clean = cleanup.Cleanup(creds=creds,
                                cleanup_file=args.cleanup_file,
                                verify=args.verify,
                                dry_run=args.dry_run,
                                names=args.names)
        clean.run()

    # Post workload
    elif args.workload == 'post':
        post_process = post.Post(filename=args.results_file,
                                 format_type=args.format,
                                 output_file=args.output_file,
                                 stat=args.stat,
                                 test=args.test,
                                 fiojob=args.fiojob,
                                 summary=args.summary,
                                 raw_mode=args.raw_mode,
                                 open_graph=args.open_graph)
        post_process.run()

    # Worker workload
    elif args.workload == 'worker':
        worker_server = cp_worker.CPWorker(args.control_ip, args.control_port)
        worker_server.run()


def controlThread(host, port):
    cp_control.run(host=host, port=int(port), debug=False)


def main():
    try:
        cp_app()
    except (exceptions.CPError, cloudpunch.ostlib.exceptions.OSTLibError) as e:
        logging.error(e.message)
    except KeyboardInterrupt:
        pass
    # except Exception as e:
    #     logging.error('%s: %s', type(e).__name__, e.message)
    finally:
        logging.info('Terminating CloudPunch')


if __name__ == '__main__':
    main()
