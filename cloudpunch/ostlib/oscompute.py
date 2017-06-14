import os
import time
import logging

import novaclient.client as nclient
import novaclient.exceptions


class BaseCompute(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the nova object which handles interaction with the API
        self.nova = nclient.Client(str(api_version),
                                   session=session,
                                   region_name=region_name)
        self.api_version = api_version


class SecGroup(BaseCompute):

    def create(self, name, description=''):
        # Create a security group with no rules
        self.group = self.nova.security_groups.create(name=name,
                                                      description=description)
        logging.debug('Created security group %s with ID %s', name, self.get_id())

    def delete(self, secgroup_id=None):
        group = self.get(secgroup_id)
        try:
            group.delete()
            logging.debug('Deleted security group %s with ID %s',
                          group.name, group.id)
            return True
        except Exception:
            logging.error('Failed to delete security group %s with ID %s',
                          group.name, group.id)
            return False

    def add_rule(self, protocol, from_port, to_port, secgroup_id=None):
        group = self.get(secgroup_id)
        self.nova.security_group_rules.create(group.id,
                                              ip_protocol=protocol,
                                              from_port=from_port,
                                              to_port=to_port)
        logging.debug('Added rule to security group %s with ID %s matching the protocol %s from %s to %s',
                      group.name, group.id, protocol, from_port, to_port)

    def remove_rule(self, rule_id, secgroup_id=None):
        group = self.get(secgroup_id)
        group.delete(rule_id)
        logging.debug('Removed rule %s from security group %s', rule_id, group.id)

    def load(self, secgroup_id):
        self.group = self.nova.security_groups.get(secgroup_id)

    def list(self, project_id=None, all_projects=False):
        if not project_id and not all_projects:
            groups = self.nova.security_groups.list()
        else:
            groups = self.nova.security_groups.list(search_opts={"all_tenants": 1})
        group_info = []
        for group in groups:
            if project_id and project_id != group.tenant_id:
                continue
            group_info.append({
                'id': group.id,
                'name': group.name
            })
        return group_info

    def list_rules(self, secgroup_id=None, use_cached=False):
        group = self.get(secgroup_id, use_cached)
        return group.security_group_rules

    def get(self, secgroup_id=None, use_cached=False):
        if secgroup_id:
            return self.nova.security_groups.get(secgroup_id)
        try:
            if use_cached:
                return self.group
            return self.nova.security_groups.get(self.get_id())
        except AttributeError:
            raise OSComputeError('No security group supplied and no cached security group')

    def get_name(self, secgroup_id=None, use_cached=False):
        group = self.get(secgroup_id, use_cached)
        return group.name

    def get_id(self):
        group = self.get(use_cached=True)
        return group.id


class KeyPair(BaseCompute):

    def create(self, name, path):
        # Create a keypair using the provided public key file
        public_key = open(os.path.expanduser(path)).read()
        self.keypair = self.nova.keypairs.create(name, public_key)
        logging.debug('Created keypair %s from file %s', name, path)

    def delete(self, keypair_name=None):
        keypair = self.get(keypair_name)
        try:
            self.nova.keypairs.delete(keypair)
            logging.debug('Deleted keypair %s', keypair.name)
            return True
        except Exception:
            logging.error('Failed to delete keypair %s', keypair.name)
            return False

    def load(self, keypair_name):
        # Load in a keypair
        self.keypair = self.nova.keypairs.get(keypair_name)

    def list(self):
        keypairs = self.nova.keypairs.list()
        pair_names = []
        for keypair in keypairs:
            pair_names.append(keypair.name)
        return pair_names

    def get(self, keypair_name=None, use_cached=False):
        if keypair_name:
            return self.nova.keypairs.get(keypair_name)
        try:
            if use_cached:
                return self.keypair
            return self.nova.keypairs.get(self.get_id())
        except AttributeError:
            raise OSComputeError('No keypair supplied and no cached keypair')

    def get_name(self):
        keypair = self.get(use_cached=True)
        return keypair.name


class Instance(BaseCompute):

    def create(self, instance_name, image_id, flavor_name, network_id,
               availability_zone=None, keypair_name=None, secgroup_id='default',
               retry_count=120, user_data=None, volume_id=None, snapshot_id=None,
               boot_from_vol=None):
        try:
            # if flavor is an ID
            flavor = self.nova.flavors.get(flavor_name)
        except Exception:
            # if flavor is a name
            flavor = self.nova.flavors.find(name=flavor_name)
        nic = [{
            'net-id': network_id
        }]
        # Create userdata
        if user_data:
            userdata = "#cloud-config\n\nruncmd:\n"
            for line in user_data:
                userdata += ' - %s\n' % line
            user_data = userdata
        # Create instance from volume
        if boot_from_vol:
            if volume_id:
                mapping = {'uuid': volume_id,
                           'source_type': 'volume',
                           'destination_type': 'volume',
                           'volume_size': boot_from_vol,
                           'delete_on_termination': True,
                           'boot_index': 0}
            elif snapshot_id:
                mapping = {'uuid': snapshot_id,
                           'source_type': 'snapshot',
                           'destination_type': 'volume',
                           'volume_size': boot_from_vol,
                           'delete_on_termination': True,
                           'boot_index': 0}
            else:
                mapping = {'uuid': image_id,
                           'source_type': 'image',
                           'destination_type': 'volume',
                           'volume_size': boot_from_vol,
                           'delete_on_termination': True,
                           'boot_index': 0}
            self.instance = self.nova.servers.create(name=instance_name,
                                                     image=None,
                                                     flavor=flavor,
                                                     key_name=keypair_name,
                                                     nics=nic,
                                                     availability_zone=availability_zone,
                                                     userdata=user_data,
                                                     security_groups=[secgroup_id],
                                                     block_device_mapping_v2=[mapping])
        # Create an instance
        else:
            self.instance = self.nova.servers.create(name=instance_name,
                                                     image=image_id,
                                                     flavor=flavor,
                                                     key_name=keypair_name,
                                                     nics=nic,
                                                     availability_zone=availability_zone,
                                                     userdata=user_data,
                                                     security_groups=[secgroup_id])
        logging.debug('Created instance %s with ID %s using image %s and flavor %s',
                      instance_name, self.get_id(), image_id, flavor_name)
        logging.debug('Waiting for instance %s with ID %s to finish building',
                      instance_name, self.get_id())
        # Wait for the instance to become active before continuing
        for _ in range(retry_count):
            srv = self.get()
            if srv.status.lower() == 'active':
                break
            if srv.status.lower() == 'error':
                raise OSComputeError('Instance %s with ID %s failed to create: %s' % (instance_name,
                                                                                      self.get_id(),
                                                                                      srv.fault['message']))
            time.sleep(2)
        srv = self.get()
        # Check if the instance is active or if the retry_count has been passed
        if srv.status.lower() != 'active':
            raise OSComputeError('Instance %s with ID %s took too long to change to active state' % (instance_name,
                                                                                                     self.get_id()))
        logging.debug('Instance %s with ID %s now in active state',
                      instance_name, self.get_id())

    def delete(self, instance_id=None):
        # Wait for the instance to become active before attempting delete
        # OpenStack will not delete an instance if it is building
        instance = self.get(instance_id)
        self.detach_volume(instance.id)
        self.remove_float(instance.id)
        for _ in range(60):
            srv = self.get(instance_id)
            if srv.status.lower() in ['active', 'error']:
                instance.delete()
                logging.debug('Deleted instance %s with ID %s',
                              instance.name, instance.id)
                return True
            time.sleep(1)
        # The instance has failed to delete
        logging.error('Failed to delete instance %s with ID %s',
                      instance.name, instance.id)
        return False

    def add_float(self, float_ip, instance_id=None):
        # Add floating IP address to instance
        instance = self.get(instance_id)
        instance.add_floating_ip(float_ip)
        logging.debug('Attached floating IP %s to instance %s with ID %s',
                      float_ip, instance.name, instance.id)

    def remove_float(self, instance_id=None):
        # Figure out if the instance has a floating IP address
        ips = self.list_ips(instance_id, include_networks=False)
        if ips['floating']:
            instance = self.get(instance_id)
            for floating_ip in ips['floating']:
                # Remove floating IP address from instance
                instance.remove_floating_ip(floating_ip)
                logging.debug('Detached floating IP %s from instance %s with ID %s',
                              floating_ip, instance.name, instance.id)

    def attach_volume(self, volume_id, instance_id=None):
        # Attach a volume to the instance
        instance = self.get(instance_id)
        self.nova.volumes.create_server_volume(instance.id, volume_id, '/dev/vdb')
        logging.debug('Attached volume %s to instance %s with ID %s',
                      volume_id, instance.name, instance.id)

    def detach_volume(self, instance_id=None):
        # Figure out if the instance has an attached volume
        instance = self.get(instance_id)
        volumes = self.nova.volumes.get_server_volumes(instance.id)
        if len(volumes) > 0:
            volume_id = volumes[0].id
            try:
                # Detach the volume from the instance
                self.nova.volumes.delete_server_volume(instance.id, volume_id)
                logging.debug('Detached volume %s from instance %s with ID %s',
                              volume_id, instance.name, instance.id)
            except novaclient.exceptions.Forbidden:
                # This is a root volume, ignore it
                pass

    def snapshot(self, image_name):
        # Create a snapshot and return it's image ID
        return self.nova.servers.create_image(self.get_id(), image_name)

    def load(self, instance_id):
        # Load in an instance
        self.instance = self.nova.servers.get(instance_id)

    def list(self, project_id=None, all_projects=False):
        if not project_id and not all_projects:
            servers = self.nova.servers.list()
        else:
            servers = []
            servers_chunk = self.nova.servers.list(search_opts={"all_tenants": 1},
                                                   limit=1000)
            while len(servers_chunk) > 0:
                servers += servers_chunk
                servers_chunk = self.nova.servers.list(search_opts={"all_tenants": 1},
                                                       limit=1000,
                                                       marker=servers_chunk[-1].id)
        server_info = []
        for server in servers:
            if project_id and project_id != server.tenant_id:
                continue
            server_info.append({
                'id': server.id,
                'name': server.name
            })
        return server_info

    def list_ips(self, instance_id=None, include_networks=True, use_cached=False):
        instance = self.get(instance_id, use_cached)
        networks = instance.addresses.keys()
        ip_info = {}
        if include_networks:
            for network in networks:
                ip_info[network] = {
                    'fixed': [],
                    'floating': []
                }
                for connection in instance.addresses[network]:
                    ip_info[network][connection['OS-EXT-IPS:type']].append(connection['addr'])
        else:
            ip_info = {
                'fixed': [],
                'floating': []
            }
            for network in networks:
                for connection in instance.addresses[network]:
                    ip_info[connection['OS-EXT-IPS:type']].append(connection['addr'])
        return ip_info

    def list_networks(self, instance_id=None, use_cached=False):
        instance = self.get(instance_id, use_cached)
        return instance.addresses.keys()

    def get(self, instance_id=None, use_cached=False):
        if instance_id:
            return self.nova.servers.get(instance_id)
        try:
            if use_cached:
                return self.instance
            return self.nova.servers.get(self.get_id())
        except AttributeError:
            raise OSComputeError('No instance supplied and no cached instance')

    def get_name(self, instance_id=None, use_cached=False):
        instance = self.get(instance_id, use_cached)
        return instance.name

    def get_id(self):
        instance = self.get(use_cached=True)
        return instance.id


class Quota(BaseCompute):

    def get(self, project_id):
        return self.nova.quotas.get(tenant_id=project_id).to_dict()


class OSComputeError(Exception):

    def __init__(self, message):
        super(OSComputeError, self).__init__(message)
        self.message = message
