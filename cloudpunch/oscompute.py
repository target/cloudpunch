import os
import time
import logging

import novaclient.client as nclient
import novaclient.exceptions


class SecGroup(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the nova object which handles interaction with the API
        self.nova = nclient.Client(str(api_version),
                                   session=session,
                                   region_name=region_name)
        self.api_version = api_version

    def create_secgroup(self, name, description=''):
        # Create a security group with no rules
        self.group = self.nova.security_groups.create(name=name,
                                                      description=description)
        logging.debug('Created security group %s with ID %s', name, self.get_id())

    def add_rule(self, protocol, from_port, to_port):
        # Add rules to the security group
        self.nova.security_group_rules.create(self.get_id(),
                                              ip_protocol=protocol,
                                              from_port=from_port,
                                              to_port=to_port)
        logging.debug('Added rule to security group %s with ID %s matching the protocol %s from %s to %s',
                      self.get_name(), self.get_id(), protocol, from_port, to_port)

    def delete_secgroup(self):
        # Delete the security group
        try:
            self.group.delete()
            logging.debug('Deleted security group %s with ID %s',
                          self.get_name(), self.get_id())
            return True
        except Exception:
            logging.error('Failed to delete security group %s with ID %s',
                          self.get_name(), self.get_id())
            return False

    def load_secgroup(self, secgroup_id):
        # Load in a security group
        self.group = self.nova.security_groups.get(secgroup_id)

    def get_name(self):
        return self.group.name

    def get_id(self):
        return self.group.id


class KeyPair(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the nova object which handles interaction with the API
        self.nova = nclient.Client(str(api_version),
                                   session=session,
                                   region_name=region_name)
        self.api_version = api_version

    def create_keypair(self, name, path):
        # Create a keypair using the provided public key file
        public_key = open(os.path.expanduser(path)).read()
        self.keypair = self.nova.keypairs.create(name, public_key)
        logging.debug('Created keypair %s from file %s', name, path)

    def delete_keypair(self):
        # Delete the keypair
        try:
            self.nova.keypairs.delete(self.keypair)
            logging.debug('Deleted keypair %s', self.get_name())
            return True
        except Exception:
            logging.error('Failed to delete keypair %s', self.get_name())
            return False

    def load_keypair(self, keypair_name):
        # Load in a keypair
        self.keypair = self.nova.keypairs.get(keypair_name)

    def get_name(self):
        return self.keypair.name


class Instance(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the nova object which handles interaction with the API
        self.nova = nclient.Client(str(api_version),
                                   session=session,
                                   region_name=region_name)
        self.api_version = api_version
        self.retry_count = 10

    def create_instance(self, instance_name, image_name, flavor_name, network_id,
                        availability_zone=None, keypair_name=None, secgroup_id=None,
                        retry_count=10, user_data=None, boot_from_vol=None):
        self.retry_count = retry_count
        try:
            # if image is an ID
            image = self.nova.images.get(image_name)
        except Exception:
            # if image is a name
            image = self.nova.images.find(name=image_name)
        try:
            # if flavor is an ID
            flavor = self.nova.flavors.get(flavor_name)
        except Exception:
            # if flavor is a name
            flavor = self.nova.flavors.find(name=flavor_name)
        nic = [{
            'net-id': network_id
        }]
        # Get the default security group if supplied is None
        if not secgroup_id:
            secgroup_id = 'default'
        # Create userdata
        if user_data:
            userdata = "#cloud-config\n\nruncmd:\n"
            for line in user_data:
                userdata += ' - %s\n' % line
            user_data = userdata
        # Create instance from volume
        if boot_from_vol:
            mapping = {'uuid': image.id,
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
        else:
            # Create an instance
            self.instance = self.nova.servers.create(name=instance_name,
                                                     image=image,
                                                     flavor=flavor,
                                                     key_name=keypair_name,
                                                     nics=nic,
                                                     availability_zone=availability_zone,
                                                     userdata=user_data,
                                                     security_groups=[secgroup_id])
        logging.debug('Created instance %s with ID %s using image %s and flavor %s',
                      instance_name, self.get_id(), image_name, flavor_name)
        logging.debug('Waiting for instance %s with ID %s to finish building',
                      instance_name, self.get_id())
        # Wait for the instance to become active before continuing
        for _ in range(retry_count):
            srv = self.nova.servers.get(self.get_id())
            if srv.status.lower() == 'active':
                break
            if srv.status.lower() == 'error':
                raise OSComputeError('Instance %s with ID %s failed to create: %s' % (instance_name,
                                                                                      self.get_id(),
                                                                                      srv.fault['message']))
            time.sleep(2)
        srv = self.nova.servers.get(self.get_id())
        # Check if the instance is active or if the retry_count has been passed
        if srv.status.lower() != 'active':
            raise OSComputeError('Instance %s with ID %s took too long to change to active state' % (instance_name,
                                                                                                     self.get_id()))
        logging.debug('Instance %s with ID %s now in active state',
                      instance_name, self.get_id())

    def delete_instance(self):
        # Wait for the instance to become active before attempting delete
        # OpenStack will not delete an instance if it is building
        for _ in range(self.retry_count):
            srv = self.nova.servers.get(self.get_id())
            if srv.status == 'ACTIVE':
                self.instance.delete()
                logging.debug('Deleted instance %s with ID %s',
                              self.get_name(), self.get_id())
                return True
            time.sleep(1)
        # The instance has failed to delete
        logging.error('Failed to delete instance %s with ID %s',
                      self.get_name(), self.get_id())
        return False

    def add_float(self, f_ip):
        # Add floating IP address to instance
        self.instance.add_floating_ip(f_ip)
        logging.debug('Attached floating IP %s to instance %s with ID %s',
                      f_ip, self.get_name(), self.get_id())

    def remove_float(self):
        # Figure out if the instance has a floating IP address
        ips = self.get_ips()
        if len(ips) > 1:
            floating_ip = ips[1]
            # Remove floating IP address from instance
            self.instance.remove_floating_ip(floating_ip)
            logging.debug('Detached floating IP %s from instance %s with ID %s',
                          floating_ip, self.get_name(), self.get_id())

    def attach_volume(self, volume_id):
        # Attach a volume to the instance
        self.nova.volumes.create_server_volume(self.get_id(), volume_id, '/dev/vdb')
        logging.debug('Attached volume %s to instance %s with ID %s',
                      volume_id, self.get_name(), self.get_id())

    def detach_volume(self):
        # Figure out if the instance has an attached volume
        volumes = self.nova.volumes.get_server_volumes(self.get_id())
        if len(volumes) > 0:
            volume_id = volumes[0].id
            try:
                # Detach the volume from the instance
                self.nova.volumes.delete_server_volume(self.get_id(), volume_id)
                logging.debug('Detached volume %s from instance %s with ID %s',
                              volume_id, self.get_name(), self.get_id())
            except novaclient.exceptions.Forbidden:
                # This is a root volume, ignore it
                pass

    def snapshot(self, image_name):
        # Create a snapshot and return it's image ID
        return self.nova.servers.create_image(self.get_id(), image_name)

    def load_instance(self, instance_id):
        # Load in an instance
        self.instance = self.nova.servers.get(instance_id)

    def get_project_instances(self):
        return self.nova.servers.list()

    def get_all_instances(self):
        servers = []
        servers_chunk = self.nova.servers.list(search_opts={"all_tenants": 1},
                                               limit=1000)
        while len(servers_chunk) > 0:
            servers += servers_chunk
            servers_chunk = self.nova.servers.list(search_opts={"all_tenants": 1},
                                                   limit=1000,
                                                   marker=servers_chunk[-1].id)
        return servers

    def get_name(self):
        return self.instance.name

    def get_id(self):
        return self.instance.id

    def get_ips(self):
        # Return instance's IP address
        # index 0 is always the private IP
        # index 1 is always the floating IP
        ips = []
        instance = self.nova.servers.ips(self.get_id())
        for server in instance:
            for ip in instance[server]:
                ips.append(ip['addr'])
        return ips


class Quota(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the nova object which handles interaction with the API
        self.nova = nclient.Client(str(api_version),
                                   session=session,
                                   region_name=region_name)
        self.api_version = api_version

    def get_quota(self, tenant_id):
        return self.nova.quotas.get(tenant_id=tenant_id).to_dict()


class OSComputeError(Exception):
    pass
