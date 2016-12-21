import logging
import argparse

import accelerator
import configuration
import environment

import credentials


LOGFORMAT = '%(asctime)-15s %(levelname)s %(message)s'
DATEFORMAT = '%Y-%m-%d %H:%M:%S'
__version__ = '1.2.0'


def cloudpunch():
    parser = argparse.ArgumentParser(prog='cloudpunch',
                                     description='Framework for OpenStack performance testing',
                                     version=__version__)
    parser.add_argument('-c',
                        '--config',
                        action='store',
                        dest='config_file',
                        default=None,
                        help='override default configuration with a config file')
    parser.add_argument('-e',
                        '--env',
                        action='store',
                        dest='env_file',
                        default=None,
                        help='override default environment with an environment file')
    parser.add_argument('-e2',
                        '--env2',
                        action='store',
                        dest='env2_file',
                        default=None,
                        help='environment for second OpenStack instance')
    parser.add_argument('-r',
                        '--openrc',
                        action='store',
                        dest='openrc_file',
                        default=None,
                        help='OpenRC file containing authentication info (default: env)')
    parser.add_argument('-r2',
                        '--openrc2',
                        action='store',
                        dest='openrc2_file',
                        default=None,
                        help='OpenRC file for second OpenStack instance')
    parser.add_argument('-m',
                        '--hostmap',
                        action='store',
                        dest='hostmap_file',
                        default=None,
                        help='file containg a hostmap to control instance location')
    parser.add_argument('-f',
                        '--flavor',
                        action='store',
                        dest='flavor_file',
                        default=None,
                        help='file containing a flavor breakdown')
    parser.add_argument('-o',
                        '--output',
                        action='store',
                        dest='output_file',
                        default=None,
                        help='file to save results to (default: stdout)')
    parser.add_argument('-p',
                        '--password',
                        action='store',
                        dest='password',
                        default=None,
                        help='password or token to login (only use when non-interactive)')
    parser.add_argument('-p2',
                        '--password2',
                        action='store',
                        dest='password2',
                        default=None,
                        help='password to login into second OpenStack instance')
    parser.add_argument('--no-env',
                        action='store_true',
                        dest='no_env',
                        help='do not use environment for authentication')
    parser.add_argument('--admin',
                        action='store_true',
                        dest='admin_mode',
                        help='enable admin mode (create own tenant and user)')
    parser.add_argument('--split',
                        action='store_true',
                        dest='split_mode',
                        help='enable split mode (two OpenStack instances)')
    parser.add_argument('--manual',
                        action='store_true',
                        dest='manual_mode',
                        help='enable manual test start (requires interactive)')
    parser.add_argument('--reuse',
                        action='store_true',
                        dest='reuse_mode',
                        help='enable reuse mode (run another test after completion, requires interactive)')
    parser.add_argument('--yaml',
                        action='store_true',
                        dest='yaml_mode',
                        help='results are yaml instead of json')
    parser.add_argument('--insecure',
                        action='store_false',
                        dest='insecure_mode',
                        help='ignore SSL failures')
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

    # Load in configuration
    config = configuration.Configuration(args.config_file, args.output_file,
                                         args.hostmap_file, args.flavor_file, args.split_mode)

    # Split mode means there is two sets of environment and authentication
    env2 = None
    if args.split_mode:
        # A second RC file is required
        if not args.openrc2_file:
            raise CPError('Split mode is enabled and missing required credentials file for second instance')
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
        creds_env2 = credentials.Credentials(args.openrc2_file, args.password2, True, True, args.admin_mode)
    creds = {
        'env1': credentials.Credentials(args.openrc_file, args.password, args.no_env, True, args.admin_mode),
        'env2': creds_env2
    }

    # Create accelerator object and run it
    acc = accelerator.Accelerator(config, creds, env, args.admin_mode, args.manual_mode,
                                  args.reuse_mode, args.yaml_mode, args.insecure_mode)
    acc.run()


def main():
    try:
        cloudpunch()
    except (CPError, configuration.ConfigError, environment.EnvError, credentials.CredError) as e:
        logging.error(e.message)
    except KeyboardInterrupt:
        pass
    finally:
        logging.info('Terminating CloudPunch')


class CPError(Exception):
    pass


if __name__ == '__main__':
    main()
