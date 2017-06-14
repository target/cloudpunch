import logging
import json
import os

import keystoneauth1

from cloudpunch.ostlib import osuser
from cloudpunch.ostlib import osnetwork
from cloudpunch.ostlib import oscompute
from cloudpunch.ostlib import osvolume


class Cleanup(object):

    def __init__(self, creds, cleanup_file, cleanup_data=None, cleanup_resources=True,
                 verify=False, dry_run=False, names=False):
        self.creds = creds
        self.cleanup_file = cleanup_file
        self.cleanup_data = cleanup_data
        self.cleanup_resources = cleanup_resources
        self.verify = verify
        self.dry_run = dry_run
        self.names = names

    def run(self):
        # We need to search for resources that cloudpunch has made
        if self.cleanup_file == 'search':
            cleanup_info = self.search_resources()
        # We have cleanup data, the cleanup_file is the name of the file to save to
        elif self.cleanup_data:
            cleanup_info = self.cleanup_data
        # We need cleanup data, load it from the cleanup_file
        else:
            # Make sure it actually exists as a file
            if not os.path.isfile(self.cleanup_file):
                raise CleanupError('The cleanup file %s does not exist' % self.cleanup_file)
            # Load in cleanup_file
            with open(self.cleanup_file) as f:
                contents = f.read()
            try:
                cleanup_info = json.loads(contents)
            except ValueError:
                raise CleanupError('Cleanup file %s is not a valid json format' % self.cleanup_file)

        if not self.dry_run:
            # Only delete resources if cleanup_resources is True
            if self.cleanup_resources:
                cleanup_info = self.clean(cleanup_info)
            # Save any left over resources
            self.check_resources(cleanup_info)

    def search_resources(self):
        # Create the OpenStack session
        session = osuser.Session(self.creds, self.verify).get_session()

        resources = {}
        # Set API versions
        versions = {
            'cinder': 2,
            'neutron': 2,
            'nova': 2,
        }
        # Set Keystone API version
        versions['keystone'] = self.creds.get_version()

        location = self.creds.get_creds()['auth_url']
        region = self.creds.get_region()
        logging.info('Searching for CloudPunch resources on %s under region %s' % (location, region))

        search_order = [
            # 'lbaas_monitors', 'lbaas_listeners', 'lbaas_pools', 'lbaas_lbs',
            # 'monitors', 'members', 'pool_vips', 'pools',
            'instances', 'volumes',
            'floaters', 'routers', 'master-network', 'server-network', 'client-network',
            'keypairs', 'secgroups',
            'users', 'projects'
        ]
        resource_breakdown = {
            'lbaas_monitors': {
                'label': 'lbaas v2 monitors',
                'object': osnetwork.lbaasMonitor(session, region, versions['neutron'])
            },
            'lbaas_listeners': {
                'label': 'lbaas v2 listeners',
                'object': osnetwork.lbaasListener(session, region, versions['neutron'])
            },
            'lbaas_pools': {
                'label': 'lbaas v2 pools',
                'object': osnetwork.lbaasPool(session, region, versions['neutron'])
            },
            'lbaas_lbs': {
                'label': 'lbaas v2 loadbalancers',
                'object': osnetwork.lbaasLB(session, region, versions['neutron'])
            },
            'monitors': {
                'label': 'loadbalancer monitors',
                'object': osnetwork.Monitor(session, region, versions['neutron'])
            },
            'members': {
                'label': 'loadbalancer members',
                'object': osnetwork.Member(session, region, versions['neutron'])
            },
            'pool_vips': {
                'label': 'loadbalancer pool vips',
                'object': osnetwork.Pool(session, region, versions['neutron'])
            },
            'pools': {
                'label': 'loadbalancer pools',
                'object': osnetwork.Pool(session, region, versions['neutron'])
            },
            'instances': {
                'label': 'instances',
                'object': oscompute.Instance(session, region, versions['nova'])
            },
            'volumes': {
                'label': 'volumes',
                'object': osvolume.Volume(session, region, versions['cinder'])
            },
            'floaters': {
                'label': 'floating ip addresses',
                'object': osnetwork.FloatingIP(session, region, versions['neutron'])
            },
            'routers': {
                'label': 'routers',
                'object': osnetwork.Router(session, region, versions['neutron'])
            },
            'master-network': {
                'label': 'master networks',
                'object': osnetwork.Network(session, region, versions['neutron'])
            },
            'server-network': {
                'label': 'server networks',
                'object': osnetwork.Network(session, region, versions['neutron'])
            },
            'client-network': {
                'label': 'client networks',
                'object': osnetwork.Network(session, region, versions['neutron'])
            },
            'keypairs': {
                'label': 'keypairs',
                'object': oscompute.KeyPair(session, region, versions['nova'])
            },
            'secgroups': {
                'label': 'security groups',
                'object': osnetwork.SecurityGroup(session, region, versions['nova'])
            },
            'users': {
                'label': 'users',
                'object': osuser.User(session, region, versions['keystone'])
            },
            'projects': {
                'label': 'projects',
                'object': osuser.Project(session, region, versions['keystone'])
            }
        }

        network_list = resource_breakdown['master-network']['object'].list()
        network_search = {
            'master-network': 'master',
            'server-network': '-s-',
            'client-network': '-c-'
        }

        for resource in search_order:
            resource_object = resource_breakdown[resource]['object']
            found_resources = []
            try:
                if 'network' not in resource:
                    resource_list = resource_object.list()
                else:
                    resource_list = network_list
            # Used to catch forbidden responses from looking for users and projects
            except keystoneauth1.exceptions.http.Forbidden:
                continue
            for current_resource in resource_list:
                # Find floating ip addresses on found instances
                if resource == 'floaters':
                    if 'instances' in resources:
                        for instance in resources['instances']:
                            ips = resource_breakdown['instances']['object'].list_ips(instance, include_networks=False)
                            if ips['floating']:
                                float_object = resource_breakdown['floaters']['object']
                                found_resources.append(float_object.get_id(ips['floating'][0]))
                                if self.names:
                                    logging.info('Found %s %s (%s)',
                                                 resource_breakdown[resource]['label'][:-1],
                                                 float_object.get_id(ips['floating'][0]),
                                                 ips['floating'][0])
                # Network search
                elif 'network' in resource:
                    if ('cloudpunch' in current_resource['name'] and
                            network_search[resource] in current_resource['name']):
                        found_resources.append(current_resource['id'])
                        if self.names:
                            logging.info('Found %s %s (%s)',
                                         resource_breakdown[resource]['label'][:-1],
                                         current_resource['id'],
                                         current_resource['name'])
                # Keypairs do not have an id, only a name
                elif resource == 'keypairs':
                    if 'cloudpunch' in current_resource:
                        found_resources.append(current_resource)
                        if self.names:
                            logging.info('Found %s %s',
                                         resource_breakdown[resource]['label'][:-1],
                                         current_resource)
                # Everything else
                elif 'cloudpunch' in current_resource['name']:
                    found_resources.append(current_resource['id'])
                    if self.names:
                        logging.info('Found %s %s (%s)',
                                     resource_breakdown[resource]['label'][:-1],
                                     current_resource['id'],
                                     current_resource['name'])
            logging.info('Found %s %s', len(found_resources), resource_breakdown[resource]['label'])
            if len(found_resources) > 0:
                resources[resource] = found_resources

        resources['api_versions'] = versions
        return resources

    def clean(self, cleanup_info):
        # Create the OpenStack session
        session = osuser.Session(self.creds, self.verify).get_session()

        # Load in API versions
        versions = cleanup_info['api_versions']
        # Set Keystone API version
        versions['keystone'] = self.creds.get_version()

        location = self.creds.get_creds()['auth_url']
        region = self.creds.get_region()
        logging.info('Cleaning up resources on %s under region %s', location, region)

        delete_order = [
            'lbaas_monitors', 'lbaas_listeners', 'lbaas_pools', 'lbaas_lbs',
            'monitors', 'members', 'pool_vips', 'pools',
            'instances', 'volumes',
            'floaters', 'routers', 'master-network', 'server-network', 'client-network',
            'keypairs', 'secgroups',
            'users', 'projects'
        ]
        resource_breakdown = {
            'lbaas_monitors': {
                'label': 'lbaas v2 monitors',
                'object': osnetwork.lbaasMonitor(session, region, versions['neutron'])
            },
            'lbaas_listeners': {
                'label': 'lbaas v2 listeners',
                'object': osnetwork.lbaasListener(session, region, versions['neutron'])
            },
            'lbaas_pools': {
                'label': 'lbaas v2 pools',
                'object': osnetwork.lbaasPool(session, region, versions['neutron'])
            },
            'lbaas_lbs': {
                'label': 'lbaas v2 loadbalancers',
                'object': osnetwork.lbaasLB(session, region, versions['neutron'])
            },
            'monitors': {
                'label': 'loadbalancer monitors',
                'object': osnetwork.Monitor(session, region, versions['neutron'])
            },
            'members': {
                'label': 'loadbalancer members',
                'object': osnetwork.Member(session, region, versions['neutron'])
            },
            'pool_vips': {
                'label': 'loadbalancer pool vips',
                'object': osnetwork.PoolVIP(session, region, versions['neutron'])
            },
            'pools': {
                'label': 'loadbalancer pools',
                'object': osnetwork.Pool(session, region, versions['neutron'])
            },
            'instances': {
                'label': 'instances',
                'object': oscompute.Instance(session, region, versions['nova'])
            },
            'volumes': {
                'label': 'volumes',
                'object': osvolume.Volume(session, region, versions['cinder'])
            },
            'floaters': {
                'label': 'floating ip addresses',
                'object': osnetwork.FloatingIP(session, region, versions['neutron'])
            },
            'routers': {
                'label': 'routers',
                'object': osnetwork.Router(session, region, versions['neutron'])
            },
            'master-network': {
                'label': 'master networks',
                'object': osnetwork.Network(session, region, versions['neutron'])
            },
            'server-network': {
                'label': 'server networks',
                'object': osnetwork.Network(session, region, versions['neutron'])
            },
            'client-network': {
                'label': 'client networks',
                'object': osnetwork.Network(session, region, versions['neutron'])
            },
            'keypairs': {
                'label': 'keypairs',
                'object': oscompute.KeyPair(session, region, versions['nova'])
            },
            'secgroups': {
                'label': 'security groups',
                'object': osnetwork.SecurityGroup(session, region, versions['nova'])
            },
            'users': {
                'label': 'users',
                'object': osuser.User(session, region, versions['keystone'])
            },
            'projects': {
                'label': 'projects',
                'object': osuser.Project(session, region, versions['keystone'])
            }
        }

        for resource in delete_order:
            if resource in cleanup_info:
                logging.info('Deleting %s', resource_breakdown[resource]['label'])
                resource_object = resource_breakdown[resource]['object']
                for resource_id in cleanup_info[resource][:]:
                    try:
                        if resource_object.delete(resource_id):
                            cleanup_info[resource].remove(resource_id)
                    except Exception:
                        cleanup_info[resource].remove(resource_id)

        return cleanup_info

    def check_resources(self, cleanup_info):
        # Check if there is anything left
        post_cleanup = False
        for label in cleanup_info:
            if len(cleanup_info[label]) > 0 and label not in ['api_versions']:
                post_cleanup = True
                break

        # Update cleanup_file if there is left over resources
        if post_cleanup:
            with open(self.cleanup_file, 'w') as f:
                f.write(json.dumps(cleanup_info))
            logging.info('CloudPunch resources still exist on OpenStack')
            logging.info('Saved deletion information to %s', self.cleanup_file)
        else:
            logging.info('All resources have been cleaned up')
            # Remove the file if nothing is left
            if os.path.isfile(self.cleanup_file):
                os.remove(self.cleanup_file)
                logging.info('Removed cleanup file %s', self.cleanup_file)


class CleanupError(Exception):

    def __init__(self, message):
        super(CleanupError, self).__init__(message)
        self.message = message
