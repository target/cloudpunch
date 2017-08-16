import logging
import argparse
import os

from cloudpunch import accelerator
from cloudpunch import cleanup
from cloudpunch import configuration
from cloudpunch import environment
from cloudpunch import post
from cloudpunch.ostlib import credentials
from cloudpunch.master import cp_master
from cloudpunch.slave import cp_slave


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
                            help='environment for second OpenStack instance')
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
                            help='OpenRC file for second OpenStack instance')
    run_parser.add_argument('-m',
                            '--hostmap',
                            action='store',
                            dest='hostmap_file',
                            default=None,
                            help='file containg a hostmap to control instance location')
    run_parser.add_argument('-f',
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
                            help='password to login into second OpenStack instance')
    run_parser.add_argument('--no-env',
                            action='store_true',
                            dest='no_env',
                            help='do not use environment for authentication')
    run_parser.add_argument('--admin',
                            action='store_true',
                            dest='admin_mode',
                            help='enable admin mode (create own tenant and user)')
    run_parser.add_argument('--split',
                            action='store_true',
                            dest='split_mode',
                            help='enable split mode (two OpenStack instances)')
    run_parser.add_argument('--manual',
                            action='store_true',
                            dest='manual_mode',
                            help='enable manual test start (requires interactive)')
    run_parser.add_argument('--reuse',
                            action='store_true',
                            dest='reuse_mode',
                            help='enable reuse mode (run another test after completion, requires interactive)')
    run_parser.add_argument('--yaml',
                            action='store_true',
                            dest='yaml_mode',
                            help='results are yaml instead of json')
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
    # Master parser
    master_parser = subparsers.add_parser('master',
                                          help='start the master server')
    master_parser.add_argument('-l',
                               '--listen',
                               action='store',
                               dest='host',
                               default='0.0.0.0',
                               help='host address to listen on (default: 0.0.0.0)')
    master_parser.add_argument('-p',
                               '--port',
                               action='store',
                               dest='port',
                               default='80',
                               help='port to listen on (default: 80)')
    master_parser.add_argument('-d',
                               '--debug',
                               action='store_true',
                               dest='debug_mode',
                               help='enable debug mode')

    # Slave parser
    slave_parser = subparsers.add_parser('slave',
                                         help='start a slave server')
    slave_parser.add_argument('master_ip',
                              help='master ip address')

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

    # Run workload
    if args.workload == 'run':
        # Load in configuration
        config = configuration.Configuration(config_file=args.config_file,
                                             output_file=args.output_file,
                                             hostmap_file=args.hostmap_file,
                                             flavor_file=args.flavor_file,
                                             split_mode=args.split_mode)

        # Split mode means there is two sets of environment and authentication
        env2 = None
        if args.split_mode:
            # A second RC file is required
            if not args.openrc2_file:
                raise CPError('Split mode is enabled but missing required credentials file for second instance')
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

        # Create authentication dictionary with both env1 and env2
        creds_env2 = None
        if args.split_mode:
            creds_env2 = credentials.Credentials(openrc_file=args.openrc2_file,
                                                 password=args.password2,
                                                 no_env=True,
                                                 interactive=True,
                                                 use_admin=args.admin_mode)
        creds = {
            'env1': credentials.Credentials(openrc_file=args.openrc_file,
                                            password=args.password,
                                            no_env=args.no_env,
                                            interactive=True,
                                            use_admin=args.admin_mode),
            'env2': creds_env2
        }

        # Create accelerator object and run it
        acc = accelerator.Accelerator(config, creds, env,
                                      admin_mode=args.admin_mode,
                                      manual_mode=args.manual_mode,
                                      reuse_mode=args.reuse_mode,
                                      yaml_mode=args.yaml_mode,
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

    # Master workload
    elif args.workload == 'master':
        cp_master.run(host=args.host,
                      port=args.port,
                      debug=args.debug_mode)

    # Slave workload
    elif args.workload == 'slave':
        slave_server = cp_slave.CPSlave(args.master_ip)
        slave_server.run()


def main():
    try:
        cp_app()
    except (CPError, configuration.ConfigError, environment.EnvError,
            credentials.CredError, cleanup.CleanupError, post.PostExcept,
            cp_slave.CPSlaveError) as e:
        logging.error(e.message)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error('%s: %s', type(e).__name__, e.message)
    finally:
        logging.info('Terminating CloudPunch')


class CPError(Exception):

    def __init__(self, message):
        super(CPError, self).__init__(message)
        self.message = message


if __name__ == '__main__':
    main()
