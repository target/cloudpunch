import logging
import json
import argparse
import os

import credentials
import osuser
import osnetwork
import oscompute
import osvolume

LOGFORMAT = '%(asctime)-15s %(levelname)s %(message)s'
DATEFORMAT = '%Y-%m-%d %H:%M:%S'
__version__ = '1.2.0'


class CleanupError(Exception):
    pass


def loadcleanup(cleanup_file):
    contents = open(cleanup_file).read()
    try:
        data = json.loads(contents)
    except ValueError:
        raise CleanupError('Cleanup file %s is not a valid json format' % cleanup_file)
    return data


def cleanup():
    parser = argparse.ArgumentParser(prog='cloudpunch-cleanup',
                                     description='CloudPunch cleanup',
                                     version=__version__)
    parser.add_argument('-f',
                        '--file',
                        action='store',
                        dest='cleanup_file',
                        default=None,
                        help='cleanup file containing resource information')
    parser.add_argument('-r',
                        '--openrc',
                        action='store',
                        dest='openrc_file',
                        default=None,
                        help='OpenRC file containing authentication info (default: env)')
    parser.add_argument('-p',
                        '--password',
                        action='store',
                        dest='password',
                        default=None,
                        help='password to login (only use when non-interactive)')
    parser.add_argument('--no-env',
                        action='store_true',
                        dest='no_env',
                        help='do not use environment for authentication')
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

    # cleanup_file is required
    if not args.cleanup_file:
        raise CleanupError('Missing cleanup file')
    # Make sure it actually exists as a file
    if not os.path.isfile(args.cleanup_file):
        raise CleanupError('The file %s does not exist' % args.cleanup_file)

    # Load in credentials
    creds = credentials.Credentials(args.openrc_file, args.password, args.no_env, True)
    # Create the OpenStack session
    session = osuser.Session(creds, args.insecure_mode).get_session()
    # Load in cleanup_file
    cleanup_info = loadcleanup(args.cleanup_file)
    # Load in API versions
    versions = cleanup_info['api_versions']
    # Set Keystone API version
    versions['keystone'] = creds.get_version()

    logging.info('Cleaning up resources')

    if 'instances' in cleanup_info:
        logging.info('Deleting instances')
        # Create an instance object
        instance = oscompute.Instance(session, creds.get_region(), versions['nova'])
        # Loop through a copy of the cleanup file
        for instance_id in cleanup_info['instances'][:]:
            try:
                # Detach volume and floating IP from instance before deleting
                # Seems to provide a more reliable delete
                instance.load_instance(instance_id)
                instance.detach_volume()
                instance.remove_float()
                # If deletion is successful, remove from cleanup file
                if instance.delete_instance():
                    cleanup_info['instances'].remove(instance_id)
            # This is to catch if there is an error or if the resource is missing
            except Exception:
                cleanup_info['instances'].remove(instance_id)

    if 'volumes' in cleanup_info:
        logging.info('Deleting volumes')
        volume = osvolume.Volume(session, creds.get_region(), versions['cinder'])
        for volume_id in cleanup_info['volumes'][:]:
            try:
                volume.load_volume(volume_id)
                if volume.delete_volume():
                    cleanup_info['volumes'].remove(volume_id)
            except Exception:
                cleanup_info['volumes'].remove(volume_id)

    if 'floaters' in cleanup_info:
        logging.info('Deleting floating ips')
        floater = osnetwork.FloatingIP(session, creds.get_region(), versions['neutron'])
        for floater_id in cleanup_info['floaters'][:]:
            try:
                floater.load_floatingip(floater_id)
                if floater.delete_floatingip():
                    cleanup_info['floaters'].remove(floater_id)
            except Exception:
                cleanup_info['floaters'].remove(floater_id)

    if 'routers' in cleanup_info:
        logging.info('Deleting routers')
        router = osnetwork.Router(session, creds.get_region(), versions['neutron'])
        for router_id in cleanup_info['routers'][:]:
            try:
                router.load_router(router_id)
                if router.delete_router():
                    cleanup_info['routers'].remove(router_id)
            except Exception:
                cleanup_info['routers'].remove(router_id)

    for role in ['master', 'server', 'client']:
        name = '%s-network' % role
        if name in cleanup_info:
            logging.info('Deleting %s networks', role)
            network = osnetwork.Network(session, creds.get_region(), versions['neutron'])
            for network_id in cleanup_info[name][:]:
                try:
                    network.load_network(network_id)
                    if network.delete_network():
                        cleanup_info[name].remove(network_id)
                except Exception:
                    cleanup_info[name].remove(network_id)

    if 'keypairs' in cleanup_info:
        logging.info('Deleting keypairs')
        keypair = oscompute.KeyPair(session, creds.get_region(), versions['nova'])
        for keypair_name in cleanup_info['keypairs'][:]:
            try:
                keypair.load_keypair(keypair_name)
                if keypair.delete_keypair():
                    cleanup_info['keypairs'].remove(keypair_name)
            except Exception:
                cleanup_info['keypairs'].remove(keypair_name)

    if 'secgroups' in cleanup_info:
        logging.info('Deleting security groups')
        secgroup = oscompute.SecGroup(session, creds.get_region(), versions['nova'])
        for secgroup_id in cleanup_info['secgroups'][:]:
            try:
                secgroup.load_secgroup(secgroup_id)
                if secgroup.delete_secgroup():
                    cleanup_info['secgroups'].remove(secgroup_id)
            except Exception:
                cleanup_info['secgroups'].remove(secgroup_id)

    if 'users' in cleanup_info:
        logging.info('Deleting users')
        user = osuser.User(session, creds.get_region(), versions['keystone'])
        for user_id in cleanup_info['users'][:]:
            try:
                user.load_user(user_id)
                if user.delete_user():
                    cleanup_info['users'].remove(user_id)
            except Exception:
                cleanup_info['users'].remove(user_id)

    if 'projects' in cleanup_info:
        logging.info('Deleting projects')
        project = osuser.Project(session, creds.get_region(), versions['keystone'])
        for project_id in cleanup_info['projects'][:]:
            try:
                project.load_project(project_id)
                if project.delete_project():
                    cleanup_info['projects'].remove(project_id)
            except Exception:
                cleanup_info['projects'].remove(project_id)

    # Check if there is anything left
    post_cleanup = False
    for label in cleanup_info:
        if len(cleanup_info[label]) > 0 and label not in ['api_versions']:
            post_cleanup = True
            break

    # Update cleanup_file if there is left over resources
    if post_cleanup:
        post_cleanup_file = open(args.cleanup_file, 'w')
        post_cleanup_file.write(json.dumps(cleanup))
        post_cleanup_file.close()
        logging.info('CloudPunch resources still exist on OpenStack. The deletion file has been updated')
        logging.info('Saved deletion information to %s', args.cleanup_file)
    # Remove the file if nothing is left
    else:
        os.remove(args.cleanup_file)
        logging.info('All resources have been cleaned up')
        logging.info('Removed cleanup file %s', args.cleanup_file)


def main():
    try:
        cleanup()
    except (CleanupError, credentials.CredError) as e:
        logging.error(e.message)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error('%s: %s', type(e).__name__, e.message)
    finally:
        logging.info('Terminating CloudPunch cleanup')


if __name__ == '__main__':
    main()
