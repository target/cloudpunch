import time
import logging

import neutronclient.v2_0.client as nclient


class Network(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the neutron object which handles interaction with the API
        self.neutron = nclient.Client(session=session,
                                      region_name=region_name)
        self.api_version = api_version

    def create_network(self, name):
        # Create dictionary containing network information
        net_body = {
            'network': {
                'name': name,
                'admin_state_up': True
            }
        }
        # Create a network
        self.network = self.neutron.create_network(net_body)
        logging.debug('Created network %s with ID %s', name, self.get_id())

    def delete_network(self):
        # Allow 10 seconds before a network fails to delete
        for _ in range(10):
            try:
                # Delete a network
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_network(self.get_id())
                logging.debug('Deleted network %s with ID %s', self.get_name(), self.get_id())
                return True
            except Exception:
                time.sleep(1)
        # The network has failed to delete
        logging.error('Failed to delete network %s with ID %s', self.get_name(), self.get_id())
        return False

    def load_network(self, network_id):
        # Load in a network
        self.network = self.neutron.show_network(network_id)

    def get_name(self):
        return self.network['network']['name']

    def get_id(self):
        return self.network['network']['id']


class ExtNetwork(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the neutron object which handles interaction with the API
        self.neutron = nclient.Client(session=session,
                                      region_name=region_name)
        self.api_version = api_version

    def find_ext_network(self, name=None):
        # Get a list of all networks
        externals = self.neutron.list_networks()['networks']
        for external in externals:
            if name:
                if external['name'] == name:
                    # Use this network because it matched the configured name
                    self.ext_network = external
                    return external
            elif external['router:external']:
                # This network was the first found that is marked external
                self.ext_network = external
                return external
        raise OSNetworkError('Unable to find external network %s' % name)

    def get_name(self):
        return self.ext_network['name']

    def get_id(self):
        return self.ext_network['id']


class Subnet(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the neutron object which handles interaction with the API
        self.neutron = nclient.Client(session=session,
                                      region_name=region_name)
        self.api_version = api_version

    def create_subnet(self, name, cidr, network_id, dns_nameservers=None):
        # Create dictionary containing subnet information
        subnet_body = {
            'subnet': {
                'name': name,
                'cidr': cidr,
                'network_id': network_id,
                'enable_dhcp': True,
                'ip_version': 4,
                'dns_nameservers': dns_nameservers
            }
        }
        # Create a subnet
        self.subnet = self.neutron.create_subnet(subnet_body)
        logging.debug('Created subnet %s (%s) with ID %s and attached to network ID %s',
                      name, cidr, self.get_id(), network_id)

    def get_name(self):
        return self.subnet['subnet']['name']

    def get_id(self):
        return self.subnet['subnet']['id']


class Router(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the neutron object which handles interaction with the API
        self.neutron = nclient.Client(session=session,
                                      region_name=region_name)
        self.api_version = api_version

    def create_router(self, name, ext_network_id):
        # Create dictionary containing router information
        router_body = {
            'router': {
                'name': name,
                'admin_state_up': True,
                'external_gateway_info': {
                    'network_id': ext_network_id
                }
            }
        }
        # Create a router
        self.router = self.neutron.create_router(router_body)
        logging.debug('Created router %s with ID %s attached to external network ID %s',
                      name, self.get_id(), ext_network_id)

    def attach_subnet(self, subnet_id):
        # Create dictionary containing subnet information
        router_int_body = {
            'subnet_id': subnet_id
        }
        # Attach subnet to router
        self.neutron.add_interface_router(self.get_id(), router_int_body)
        logging.debug('Attached router %s to subnet ID %s', self.get_name(), subnet_id)

    def delete_router(self):
        subnets = []
        # Find attached subnets via port list
        for port in self.neutron.list_ports()['ports']:
            if (port['device_id'] == self.get_id() and
                    '169.254' not in port['fixed_ips'][0]['ip_address'] and
                    port['device_owner'] != 'network:router_gateway'):
                subnets.append(port['fixed_ips'][0]['subnet_id'])
        try:
            for subnet_id in subnets:
                # Create dictionary containing subnet information
                router_body = {
                    'subnet_id': subnet_id
                }
                # Detach subnet from router
                # Allow 5 seconds before a subnet fails to detach
                for _ in range(5):
                    try:
                        self.neutron.remove_interface_router(self.get_id(), router_body)
                        logging.debug('Detached subnet ID %s from router %s', subnet_id, self.get_name())
                        break
                    except Exception:
                        time.sleep(1)
            # Detach the router's gateway
            self.neutron.remove_gateway_router(self.get_id())
            # Delete the router
            self.neutron.delete_router(self.get_id())
            logging.debug('Deleted router %s with ID %s', self.get_name(), self.get_id())
            return True
        except Exception:
            logging.error('Failed to delete router %s with ID %s', self.get_name(), self.get_id())
            return False

    def load_router(self, router_id):
        # Load in a router
        self.router = self.neutron.show_router(router_id)

    def get_name(self):
        return self.router['router']['name']

    def get_id(self):
        return self.router['router']['id']


class FloatingIP(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the neutron object which handles interaction with the API
        self.neutron = nclient.Client(session=session,
                                      region_name=region_name)
        self.api_version = api_version

    def create_floatingip(self, ext_network_id):
        # Create dictionary containing external network information
        float_body = {
            'floatingip': {
                'floating_network_id': ext_network_id
            }
        }
        # Reserve a floating IP
        self.floating_ip = self.neutron.create_floatingip(float_body)
        logging.debug('Allocated floating IP %s with ID %s on external network ID %s',
                      self.get_ip(), self.get_id(), ext_network_id)

    def delete_floatingip(self):
        # Allow 10 seconds before a floating IP fails to release
        for _ in range(10):
            try:
                # Release a floating IP address
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_floatingip(self.get_id())
                logging.debug('Released floating IP %s with ID %s', self.get_ip(), self.get_id())
                return True
            except Exception:
                time.sleep(1)
        # The floating IP address failed to release
        logging.error('Failed to release floating IP %s with ID %s', self.get_ip(), self.get_id())
        return False

    def load_floatingip(self, floatingip_id):
        # Load a floating IP address
        self.floating_ip = self.neutron.show_floatingip(floatingip_id)

    def get_ip(self):
        return self.floating_ip['floatingip']['floating_ip_address']

    def get_id(self):
        return self.floating_ip['floatingip']['id']


class OSNetworkError(Exception):
    pass
