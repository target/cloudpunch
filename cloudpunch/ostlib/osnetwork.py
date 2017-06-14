import time
import logging

import neutronclient.v2_0.client as nclient


class BaseNetwork(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the neutron object which handles interaction with the API
        self.neutron = nclient.Client(session=session,
                                      region_name=region_name)
        self.session = session
        self.api_version = api_version


class SecurityGroup(BaseNetwork):

    def create(self, name, description=''):
        sec_body = {
            'security_group': {
                'name': name,
                'description': description
            }
        }
        self.group = self.neutron.create_security_group(sec_body)
        logging.debug('Created security group %s with ID %s', name, self.get_id())

    def delete(self, secgroup_id=None):
        group = self.get(secgroup_id)
        try:
            self.neutron.delete_security_group(group['security_group']['id'])
            logging.debug('Deleted security group %s with ID %s',
                          group['security_group']['name'], group['security_group']['id'])
            return True
        except Exception:
            logging.error('Failed to delete security group %s with ID %s',
                          group['security_group']['name'], group['security_group']['id'])
            return False

    def add_rule(self, protocol, from_port, to_port, secgroup_id=None):
        group = self.get(secgroup_id)
        if protocol.lower() == 'icmp':
            from_port = None
            to_port = None
        rule_body = {
            'security_group_rule': {
                'direction': 'ingress',
                'protocol': protocol,
                'port_range_min': from_port,
                'port_range_max': to_port,
                'ethertype': 'IPv4',
                'remote_ip_prefix': '0.0.0.0/0',
                'security_group_id': group['security_group']['id']
            }
        }
        self.neutron.create_security_group_rule(rule_body)
        logging.debug('Added rule to security group %s with ID %s matching the protocol %s from %s to %s',
                      group['security_group']['name'], group['security_group']['id'], protocol, from_port, to_port)

    def remove_rule(self, rule_id):
        self.neutron.delete_security_group_rule(rule_id)
        logging.debug('Removed security group rule %s', rule_id)

    def load(self, secgroup_id):
        self.group = self.neutron.show_security_group(secgroup_id)

    def list(self, project_id=None, all_projects=False):
        group_info = []
        groups = self.neutron.list_security_groups()['security_groups']
        for group in groups:
            if not all_projects and project_id and group['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and group['tenant_id'] != self.session.get_project_id():
                continue
            group_info.append({
                'id': group['id'],
                'name': group['name']
            })
        return group_info

    def list_rules(self, secgroup_id=None):
        rules_info = []
        group = self.get(secgroup_id)
        rules = self.neutron.list_security_group_rules()['security_group_rules']
        for rule in rules:
            if rule['security_group_id'] == group['security_group']['id']:
                rules_info.append(rule)
        return rules_info

    def get(self, secgroup_id=None, use_cached=False):
        if secgroup_id:
            return self.neutron.show_security_group(secgroup_id)
        try:
            if use_cached:
                return self.group
            return self.neutron.show_security_group(self.get_id())
        except AttributeError:
            raise OSNetworkError('No security group supplied and no cached network')

    def get_name(self, secgroup_id=None, use_cached=False):
        group = self.get(secgroup_id, use_cached)
        return group['security_group']['name']

    def get_id(self):
        group = self.get(use_cached=True)
        return group['security_group']['id']


class Network(BaseNetwork):

    def create(self, name):
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

    def delete(self, network_id=None):
        network = self.get(network_id)
        # Allow 10 seconds before a network fails to delete
        for _ in range(10):
            try:
                # Delete a network
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_network(network['network']['id'])
                logging.debug('Deleted network %s with ID %s',
                              network['network']['name'], network['network']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The network has failed to delete
        logging.error('Failed to delete network %s with ID %s',
                      network['network']['name'], network['network']['id'])
        return False

    def load(self, network_id):
        self.network = self.neutron.show_network(network_id)

    def list(self, project_id=None, all_projects=False, include_external=False):
        network_info = []
        networks = self.neutron.list_networks()['networks']
        for network in networks:
            if not all_projects and project_id and network['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and network['tenant_id'] != self.session.get_project_id():
                continue
            network_info.append({
                'id': network['id'],
                'name': network['name']
            })
        return network_info

    def list_subnets(self, network_id=None, use_cached=False):
        network = self.get(network_id)
        return network['network']['subnets']

    def get(self, network_id=None, use_cached=False):
        if network_id:
            return self.neutron.show_network(network_id)
        try:
            if use_cached:
                return self.network
            return self.neutron.show_network(self.get_id())
        except AttributeError:
            raise OSNetworkError('No network supplied and no cached network')

    def get_name(self, network_id=None, use_cached=False):
        network = self.get(network_id, use_cached)
        return network['network']['name']

    def get_id(self):
        network = self.get(use_cached=True)
        return network['network']['id']


class ExtNetwork(BaseNetwork):

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

    def list(self):
        external_info = []
        networks = self.neutron.list_networks()['networks']
        for network in networks:
            if network['router:external']:
                external_info.append({
                    'id': network['id'],
                    'name': network['name']
                })
        return external_info

    def get(self):
        try:
            return self.ext_network
        except AttributeError:
            raise OSNetworkError('No cached external network')

    def get_name(self):
        ext_network = self.get()
        return ext_network['name']

    def get_id(self):
        ext_network = self.get()
        return ext_network['id']


class Subnet(BaseNetwork):

    def create(self, name, cidr, network_id, dns_nameservers=None):
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

    def load(self, subnet_id):
        self.subnet = self.neutron.show_subnet(subnet_id)

    def list(self, project_id=None, all_projects=False):
        subnet_info = []
        subnets = self.neutron.list_subnets()['subnets']
        for subnet in subnets:
            if not all_projects and project_id and subnet['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and subnet['tenant_id'] != self.session.get_project_id():
                continue
            subnet_info.append({
                'id': subnet['id'],
                'name': subnet['name']
            })
        return subnet_info

    def get(self, subnet_id=None, use_cached=False):
        if subnet_id:
            return self.neutron.show_subnet(subnet_id)
        try:
            if use_cached:
                return self.subnet
            return self.neutron.show_subnet(self.get_id())
        except AttributeError:
            raise OSNetworkError('No subnet supplied and no cached subnet')

    def get_name(self, subnet_id=None, use_cached=False):
        subnet = self.get(subnet_id, use_cached)
        return subnet['subnet']['name']

    def get_id(self):
        subnet = self.get(use_cached=True)
        return subnet['subnet']['id']


class Port(BaseNetwork):

    def create(self, network_id, name, description='', device_id=None, allowed_address_pairs=None):
        # Create dictionary containing port information
        port_body = {
            'port': {
                'network_id': network_id,
                'name': name,
                'description': description
            }
        }
        if device_id:
            port_body['device_id'] = device_id
        if allowed_address_pairs:
            port_body['allowed_address_pairs'] = allowed_address_pairs
        # Create a port
        self.port = self.neutron.create_port(port_body)
        logging.debug('Created port %s with ID %s and attached to network ID %s',
                      name, self.get_id(), network_id)

    def delete(self, port_id=None):
        port = self.get(port_id)
        # Allow 10 seconds before a port fails to delete
        for _ in range(10):
            try:
                # Delete a port
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_port(port['port']['id'])
                logging.debug('Deleted port %s', port['port']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The port has failed to delete
        logging.error('Failed to delete port %s', port['port']['id'])
        return False

    def load(self, port_id):
        self.port = self.neutron.show_port(port_id)

    def list(self, project_id=None, all_projects=False):
        port_info = []
        ports = self.neutron.list_ports()['ports']
        for port in ports:
            if not all_projects and project_id and port['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and port['tenant_id'] != self.session.get_project_id():
                continue
            port_info.append({
                'id': port['id'],
                'name': port['name']
            })
        return port_info

    def get(self, port_id=None, use_cached=False):
        if port_id:
            return self.neutron.show_port(port_id)
        try:
            if use_cached:
                return self.port
            return self.neutron.show_port(self.get_id())
        except AttributeError:
            raise OSNetworkError('No port supplied and no cached port')

    def get_name(self, port_id=None, use_cached=False):
        port = self.get(port_id, use_cached)
        return port['port']['name']

    def get_id(self):
        port = self.get(use_cached=True)
        return port['port']['id']


class Router(BaseNetwork):

    def create(self, name, ext_network_id):
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

    def delete(self, router_id=None):
        router = self.get(router_id)
        subnets = []
        # Find attached subnets via port list
        for port in self.neutron.list_ports()['ports']:
            if (port['device_id'] == router['router']['id'] and
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
                        self.neutron.remove_interface_router(router['router']['id'], router_body)
                        logging.debug('Detached subnet ID %s from router %s', subnet_id, router['router']['name'])
                        break
                    except Exception:
                        time.sleep(1)
            # Detach the router's gateway
            self.neutron.remove_gateway_router(router['router']['id'])
            # Delete the router
            self.neutron.delete_router(router['router']['id'])
            logging.debug('Deleted router %s with ID %s', router['router']['name'], router['router']['id'])
            return True
        except Exception:
            logging.error('Failed to delete router %s with ID %s', router['router']['name'], router['router']['id'])
            return False

    def attach_subnet(self, subnet_id, router_id=None):
        router = self.get(router_id)
        # Create dictionary containing subnet information
        router_int_body = {
            'subnet_id': subnet_id
        }
        # Attach subnet to router
        self.neutron.add_interface_router(router['router']['id'], router_int_body)
        logging.debug('Attached router %s to subnet ID %s', router['router']['name'], subnet_id)

    def load(self, router_id):
        self.router = self.neutron.show_router(router_id)

    def list(self, project_id=None, all_projects=False):
        router_info = []
        routers = self.neutron.list_routers()['routers']
        for router in routers:
            if not all_projects and project_id and router['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and router['tenant_id'] != self.session.get_project_id():
                continue
            router_info.append({
                'id': router['id'],
                'name': router['name']
            })
        return router_info

    def get(self, router_id=None, use_cached=False):
        if router_id:
            return self.neutron.show_router(router_id)
        try:
            if use_cached:
                return self.router
            return self.neutron.show_router(self.get_id())
        except AttributeError:
            raise OSNetworkError('No router supplied and no cached router')

    def get_name(self, router_id=None, use_cached=False):
        router = self.get(router_id, use_cached)
        return router['router']['name']

    def get_id(self):
        router = self.get(use_cached=True)
        return router['router']['id']


class FloatingIP(BaseNetwork):

    def create(self, ext_network_id, port_id=None):
        # Create dictionary containing external network information
        float_body = {
            'floatingip': {
                'floating_network_id': ext_network_id
            }
        }
        if port_id:
            float_body['floatingip']['port_id'] = port_id
        # Reserve a floating IP
        self.floating_ip = self.neutron.create_floatingip(float_body)
        logging.debug('Allocated floating IP %s with ID %s on external network ID %s',
                      self.get_ip(), self.get_id(), ext_network_id)

    def delete(self, floatingip_id=None):
        floating_ip = self.get(floatingip_id)
        self.disassociate(floating_ip['floatingip']['id'])
        # Allow 10 seconds before a floating IP fails to release
        for _ in range(10):
            try:
                # Release a floating IP address
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_floatingip(floating_ip['floatingip']['id'])
                logging.debug('Released floating IP %s with ID %s',
                              floating_ip['floatingip']['floating_ip_address'], floating_ip['floatingip']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The floating IP address failed to release
        logging.error('Failed to release floating IP %s with ID %s',
                      floating_ip['floatingip']['floating_ip_address'], floating_ip['floatingip']['id'])
        return False

    def disassociate(self, floatingip_id=None):
        floating_ip = self.get(floatingip_id)
        if floating_ip['floatingip']['port_id']:
            float_body = {
                'floatingip': {
                    'port_id': None
                }
            }
            self.neutron.update_floatingip(floating_ip['floatingip']['id'], float_body)
            logging.debug('Disassociated floating ip %s from port %s',
                          floating_ip['floatingip']['floating_ip_address'],
                          floating_ip['floatingip']['port_id'])

    def load(self, floatingip_id):
        self.floating_ip = self.neutron.show_floatingip(floatingip_id)

    def list(self, project_id=None, all_projects=False):
        floatingip_info = []
        floatingips = self.neutron.list_floatingips()['floatingips']
        for floatingip in floatingips:
            if not all_projects and project_id and floatingip['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and floatingip['tenant_id'] != self.session.get_project_id():
                continue
            floatingip_info.append({
                'id': floatingip['id'],
                'ip': floatingip['floating_ip_address']
            })
        return floatingip_info

    def get(self, floatingip_id=None, use_cached=False):
        if floatingip_id:
            return self.neutron.show_floatingip(floatingip_id)
        try:
            if use_cached:
                return self.floating_ip
            return self.neutron.show_floatingip(self.get_id())
        except AttributeError:
            raise OSNetworkError('No floating ip supplied and no cached floating ip')

    def get_ip(self, floatingip_id=None, use_cached=False):
        ip = self.get(floatingip_id, use_cached)
        return ip['floatingip']['floating_ip_address']

    def get_id(self, floating_ip=None):
        if floating_ip:
            floats = self.neutron.list_floatingips()['floatingips']
            for floater in floats:
                if floater['floating_ip_address'] == floating_ip:
                    return floater['id']
            raise OSNetworkError('Floating ip address %s not found', floating_ip)
        else:
            ip = self.get(use_cached=True)
            return ip['floatingip']['id']


class Pool(BaseNetwork):

    def create(self, name, method, protocol, subnet_id, description=''):
        method = method.upper()
        if method not in ['ROUND_ROBIN', 'LEAST_CONNECTIONS', 'SOURCE_IP']:
            raise OSNetworkError('%s is not a valid method. Must be ROUND_ROBIN, LEAST_CONNECTIONS, or SOURCE_IP')
        protocol = protocol.upper()
        if protocol not in ['HTTP', 'HTTPS', 'TCP']:
            raise OSNetworkError('%s is not a valid protocol. Must be HTTP, HTTPS, or TCP' % protocol)
        pool_body = {
            'pool': {
                'name': name,
                'lb_method': method,
                'protocol': protocol,
                'subnet_id': subnet_id,
                'description': description
            }
        }
        self.pool = self.neutron.create_pool(pool_body)
        logging.debug('Created loadbalancer pool %s with ID %s', name, self.get_id())

    def delete(self, pool_id=None):
        pool = self.get(pool_id)
        self.disassociate_monitors(pool['pool']['id'])
        # Allow 10 seconds before a pool fails to delete
        for _ in range(10):
            try:
                # Delete a pool
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_pool(pool['pool']['id'])
                logging.debug('Deleted loadbalancer pool %s with ID %s',
                              pool['pool']['name'], pool['pool']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The network has failed to delete
        logging.error('Failed to delete loadbalancer pool %s with ID %s',
                      pool['pool']['name'], pool['pool']['id'])
        return False

    def associate_monitor(self, monitor_id, pool_id=None):
        pool = self.get(pool_id)
        associate_body = {
            'health_monitor': {
                'id': monitor_id
            }
        }
        self.neutron.associate_health_monitor(pool['pool']['id'], associate_body)
        logging.debug('Associated loadbalancer monitor %s to pool %s',
                      monitor_id, pool['pool']['id'])

    def disassociate_monitor(self, monitor_id, pool_id=None):
        pool = self.get(pool_id)
        self.neutron.disassociate_health_monitor(pool['pool']['id'], monitor_id)
        logging.debug('Disassociated loadbalancer monitor %s from pool %s',
                      monitor_id, pool['pool']['id'])

    def disassociate_monitors(self, pool_id=None):
        pool = self.get(pool_id)
        monitors = self.list_associated_monitors(pool['pool']['id'])
        for monitor in monitors:
            self.disassociate_monitor(monitor, pool['pool']['id'])
        logging.debug('Disassociated ALL monitors from pool %s', pool['pool']['id'])

    def load(self, pool_id):
        self.pool = self.neutron.show_pool(pool_id)

    def list(self, project_id=None, all_projects=False):
        pool_info = []
        pools = self.neutron.list_pools()['pools']
        for pool in pools:
            if not all_projects and project_id and pool['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and pool['tenant_id'] != self.session.get_project_id():
                continue
            pool_info.append({
                'id': pool['id'],
                'name': pool['name']
            })
        return pool_info

    def list_associated_monitors(self, pool_id=None, use_cached=False):
        pool = self.get(pool_id, use_cached)
        return pool['pool']['health_monitors']

    def get(self, pool_id=None, use_cached=False):
        if pool_id:
            return self.neutron.show_pool(pool_id)
        try:
            if use_cached:
                return self.pool
            return self.neutron.show_pool(self.get_id())
        except AttributeError:
            raise OSNetworkError('No pool supplied and no cached pool')

    def get_name(self, pool_id=None, use_cached=False):
        pool = self.get(pool_id, use_cached)
        return pool['pool']['name']

    def get_id(self):
        pool = self.get(use_cached=True)
        return pool['pool']['id']


class PoolVIP(BaseNetwork):

    def create(self, name, protocol_port, protocol, subnet_id, pool_id, description='',
               session_persistence=None, connection_limit=None):
        protocol = protocol.upper()
        if protocol not in ['HTTP', 'HTTPS', 'TCP']:
            raise OSNetworkError('%s is not a valid protocol. Must be HTTP, HTTPS, or TCP')
        vip_body = {
            'vip': {
                'name': name,
                'protocol_port': protocol_port,
                'protocol': protocol,
                'subnet_id': subnet_id,
                'pool_id': pool_id,
                'description': description
            }
        }
        if session_persistence:
            session_persistence = session_persistence.upper()
            if session_persistence not in ['SOURCE_IP', 'HTTP_COOKIE', 'APP_COOKIE']:
                raise OSNetworkError('%s is not a valid protocol. Mut be SOURCE_IP, HTTP_COOKIE, or APP_COOKIE')
            vip_body['vip']['session_persistence'] = session_persistence
        if connection_limit:
            vip_body['vip']['connection_limit'] = connection_limit
        self.vip = self.neutron.create_vip(vip_body)
        logging.debug('Created pool VIP %s with ID %s', name, self.get_id())

    def delete(self, vip_id=None):
        vip = self.get(vip_id)
        # Allow 10 seconds before a vip fails to delete
        for _ in range(10):
            try:
                # Delete a vip
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_vip(vip['vip']['id'])
                logging.debug('Deleted loadbalancer vip %s with ID %s',
                              vip['vip']['name'], vip['vip']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The pool vip has failed to delete
        logging.error('Failed to delete loadbalancer vip %s with ID %s',
                      vip['vip']['name'], vip['vip']['id'])
        return False

    def load(self, vip_id):
        self.vip = self.neutron.show_vip(vip_id)

    def list(self, project_id=None, all_projects=False):
        vip_info = []
        vips = self.neutron.list_vips()['vips']
        for vip in vips:
            if not all_projects and project_id and vip['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and vip['tenant_id'] != self.session.get_project_id():
                continue
            vip_info.append({
                'id': vip['id'],
                'name': vip['name']
            })
        return vip_info

    def get(self, vip_id=None, use_cached=False):
        if vip_id:
            return self.neutron.show_vip(vip_id)
        try:
            if use_cached:
                return self.vip
            return self.neutron.show_vip(self.get_id())
        except AttributeError:
            raise OSNetworkError('No pool vip supplied and no cached pool vip')

    def get_vip_address(self, vip_id=None, use_cached=False):
        vip = self.get(vip_id, use_cached)
        return vip['vip']['address']

    def get_vip_port(self, vip_id=None, use_cached=False):
        vip = self.get(vip_id, use_cached)
        return vip['vip']['port_id']

    def get_name(self, vip_id=None, use_cached=False):
        vip = self.get(vip_id, use_cached)
        return vip['vip']['name']

    def get_id(self):
        vip = self.get(use_cached=True)
        return vip['vip']['id']


class Member(BaseNetwork):

    def create(self, instance_ip, pool_id, protocol_port, weight=1):
        member_body = {
            'member': {
                'address': instance_ip,
                'pool_id': pool_id,
                'protocol_port': protocol_port,
                'weight': weight
            }
        }
        self.member = self.neutron.create_member(member_body)
        logging.debug('Created loadbalancer member %s attached to pool %s',
                      self.get_id(), pool_id)

    def delete(self, member_id=None):
        member = self.get(member_id)
        # Allow 10 seconds before a member fails to delete
        for _ in range(10):
            try:
                # Delete a member
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_member(member['member']['id'])
                logging.debug('Deleted loadbalancer member %s', member['member']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The member has failed to delete
        logging.error('Failed to delete loadbalancer member %s', member['member']['id'])
        return False

    def load(self, member_id):
        self.member = self.neutron.show_member(member_id)

    def list(self, project_id=None, all_projects=False):
        member_info = []
        members = self.neutron.list_members()['members']
        for member in members:
            if not all_projects and project_id and member['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and member['tenant_id'] != self.session.get_project_id():
                continue
            member_info.append(member['id'])
        return member_info

    def get(self, member_id=None, use_cached=False):
        if member_id:
            return self.neutron.show_member(member_id)
        try:
            if use_cached:
                return self.member
            return self.neutron.show_member(self.get_id())
        except AttributeError:
            raise OSNetworkError('No member supplied and no cached member')

    def get_id(self):
        member = self.get(use_cached=True)
        return member['member']['id']


class Monitor(BaseNetwork):

    def create(self, monitor_type, delay=5, timeout=5, max_retries=3,
               http_method='GET', url_path='/', expected_codes='200'):
        monitor_type = monitor_type.upper()
        if monitor_type not in ['PING', 'TCP', 'HTTP', 'HTTPS']:
            raise OSNetworkError('%s is not a valid monitor type. Must be PING, TCP, HTTP, or HTTPS' % monitor_type)
        monitor_body = {
            'health_monitor': {
                'type': monitor_type,
                'delay': delay,
                'timeout': timeout,
                'max_retries': max_retries
            }
        }
        if monitor_type in ['HTTP', 'HTTPS']:
            if not url_path or url_path[0] != '/':
                raise OSNetworkError('Monitor type %s requires a URL path starting with \'/\'' % monitor_type)
            monitor_body['health_monitor']['http_method'] = http_method
            monitor_body['health_monitor']['url_path'] = url_path
            monitor_body['health_monitor']['expected_codes'] = expected_codes
        self.monitor = self.neutron.create_health_monitor(monitor_body)
        logging.debug('Created loadbalancer health monitor %s', self.get_id())

    def delete(self, monitor_id=None):
        monitor = self.get(monitor_id)
        # Disassociate all pools from monitor before deleting
        for pool in monitor['health_monitor']['pools']:
            self.neutron.disassociate_health_monitor(pool['pool_id'], monitor['health_monitor']['id'])
        # Allow 10 seconds before a monitor fails to delete
        for _ in range(10):
            try:
                # Delete a monitor
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_health_monitor(monitor['health_monitor']['id'])
                logging.debug('Deleted loadbalancer monitor %s', monitor['health_monitor']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The monitor has failed to delete
        logging.error('Failed to delete loadbalancer monitor %s', monitor['health_monitor']['id'])
        return False

    def load(self, monitor_id):
        self.monitor = self.neutron.show_health_monitor(monitor_id)

    def list(self, project_id=None, all_projects=False):
        monitor_info = []
        monitors = self.neutron.list_health_monitors()['health_monitors']
        for monitor in monitors:
            if not all_projects and project_id and monitor['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and monitor['tenant_id'] != self.session.get_project_id():
                continue
            monitor_info.append(monitor['id'])
        return monitor_info

    def get(self, monitor_id=None, use_cached=False):
        if monitor_id:
            return self.neutron.show_health_monitor(monitor_id)
        try:
            if use_cached:
                return self.monitor
            return self.neutron.show_health_monitor(self.get_id())
        except AttributeError:
            raise OSNetworkError('No monitor supplied and no cached monitor')

    def get_id(self):
        monitor = self.get(use_cached=True)
        return monitor['health_monitor']['id']


class lbaasLB(BaseNetwork):

    def create(self, name, subnet_id, description=''):
        lb_body = {
            'loadbalancer': {
                'name': name,
                'description': description,
                'vip_subnet_id': subnet_id
            }
        }
        self.lb = self.neutron.create_loadbalancer(lb_body)
        logging.debug('Created loadbalancer %s with ID %s',
                      name, self.get_id())

    def delete(self, loadbalancer_id=None):
        lb = self.get(loadbalancer_id)
        # Allow 10 seconds before a loadbalancer fails to delete
        for _ in range(10):
            try:
                # Delete a loadbalancer
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_loadbalancer(lb['loadbalancer']['id'])
                logging.debug('Deleted loadbalancer %s', lb['loadbalancer']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The loadbalancer has failed to delete
        logging.error('Failed to delete loadbalancer %s', lb['loadbalancer']['id'])
        return False

    def load(self, loadbalancer_id):
        self.lb = self.neutron.show_loadbalancer(loadbalancer_id)

    def list(self, project_id=None, all_projects=False):
        lb_info = []
        lbs = self.neutron.list_loadbalancers()['loadbalancers']
        for lb in lbs:
            if not all_projects and project_id and lb['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and lb['tenant_id'] != self.session.get_project_id():
                continue
            lb_info.append({
                'id': lb['id'],
                'name': lb['name']
            })
        return lb_info

    def get(self, loadbalancer_id=None, use_cached=False):
        if loadbalancer_id:
            return self.neutron.show_loadbalancer(loadbalancer_id)
        try:
            if use_cached:
                return self.lb
            return self.neutron.show_loadbalancer(self.get_id())
        except AttributeError:
            raise OSNetworkError('No loadbalancer supplied and no cached loadbalancer')

    def get_vip_address(self, loadbalancer_id=None, use_cached=False):
        lb = self.get(loadbalancer_id, use_cached)
        return lb['loadbalancer']['vip_address']

    def get_vip_port(self, loadbalancer_id=None, use_cached=False):
        lb = self.get(loadbalancer_id, use_cached)
        return lb['loadbalancer']['vip_port_id']

    def get_name(self, loadbalancer_id=None, use_cached=False):
        lb = self.get(loadbalancer_id, use_cached)
        return lb['loadbalancer']['name']

    def get_id(self):
        lb = self.get(use_cached=True)
        return lb['loadbalancer']['id']


class lbaasListener(BaseNetwork):

    def create(self, name, loadbalancer_id, default_pool_id, protocol,
               protocol_port, description='', connection_limit=None):
        protocol = protocol.upper()
        if protocol not in ['HTTP', 'TCP']:
            raise OSNetworkError('%s is not a valid listener protocol. Must be HTTP or TCP')
        listener_body = {
            'listener': {
                'name': name,
                'description': description,
                'loadbalancer_id': loadbalancer_id,
                'default_pool_id': default_pool_id,
                'protocol': protocol,
                'protocol_port': protocol_port
            }
        }
        if connection_limit:
            listener_body['listener']['connection_limit'] = connection_limit
        # Allow time before a listener fails to create
        for _ in range(30):
            try:
                # Create a lbaas listener
                # This may throw an exception, ignore it and wait 1 second
                self.listener = self.neutron.create_listener(listener_body)
                logging.debug('Created loadbalancer listener %s with ID %s',
                              name, self.get_id())
                return True
            except Exception:
                time.sleep(1)
        # The lbaas listener has failed to create
        logging.error('Failed to create lbaas listener %s', name)
        return False

    def delete(self, listener_id=None):
        listener = self.get(listener_id)
        # Allow 10 seconds before a listener fails to delete
        for _ in range(10):
            try:
                # Delete a listener
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_listener(listener['listener']['id'])
                logging.debug('Deleted loadbalancer listener %s', listener['listener']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The listener has failed to delete
        logging.error('Failed to delete loadbalancer listener %s', listener['listener']['id'])
        return False

    def load(self, listener_id):
        self.listener = self.neutron.show_listener(listener_id)

    def list(self, project_id=None, all_projects=False):
        listener_info = []
        listeners = self.neutron.list_listeners()['listeners']
        for listener in listeners:
            if not all_projects and project_id and listener['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and listener['tenant_id'] != self.session.get_project_id():
                continue
            listener_info.append({
                'id': listener['id'],
                'name': listener['name']
            })
        return listener_info

    def get(self, listener_id=None, use_cached=False):
        if listener_id:
            return self.neutron.show_listener(listener_id)
        try:
            if use_cached:
                return self.listener
            return self.neutron.show_listener(self.get_id())
        except AttributeError:
            raise OSNetworkError('No listener supplied and no cached listener')

    def get_name(self, listener_id=None, use_cached=False):
        listener = self.get(listener_id, use_cached)
        return listener['listener']['name']

    def get_id(self):
        listener = self.get(use_cached=True)
        return listener['listener']['id']


class lbaasPool(BaseNetwork):

    def create(self, name, method, protocol, loadbalancer_id, description=''):
        method = method.upper()
        if method not in ['ROUND_ROBIN', 'LEAST_CONNECTIONS', 'SOURCE_IP']:
            raise OSNetworkError('%s is not a valid pool method. Must be ROUND_ROBIN, LEAST_CONNECTIONS, or SOURCE_IP')
        protocol = protocol.upper()
        if protocol not in ['TCP', 'HTTPS', 'HTTP']:
            raise OSNetworkError('%s is not a valid protocol. Must be TCP, HTTP, or HTTPS')
        pool_body = {
            'pool': {
                'name': name,
                'description': description,
                'protocol': protocol,
                'lb_algorithm': method,
                'loadbalancer_id': loadbalancer_id
            }
        }
        # Allow time before a pool fails to create
        for _ in range(30):
            try:
                # Create a lbaas pool
                # This may throw an exception, ignore it and wait 1 second
                self.pool = self.neutron.create_lbaas_pool(pool_body)
                logging.debug('Created lbaas pool %s with ID %s',
                              name, self.get_id())
                return True
            except Exception:
                time.sleep(1)
        # The lbaas pool has failed to create
        logging.error('Failed to create lbaas pool %s', name)
        return False

    def delete(self, pool_id=None):
        pool = self.get(pool_id)
        self.delete_members(pool['pool']['id'])
        # Allow 10 seconds before a pool fails to delete
        for _ in range(10):
            try:
                # Delete a pool
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_lbaas_pool(pool['pool']['id'])
                logging.debug('Deleted loadbalancer pool %s', pool['pool']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The pool has failed to delete
        logging.error('Failed to delete loadbalancer pool %s', pool['pool']['id'])
        return False

    def add_member(self, instance_ip, protocol_port, subnet_id, weight=None, pool_id=None):
        pool = self.get(pool_id)
        member_body = {
            'member': {
                'address': instance_ip,
                'protocol_port': protocol_port,
                'subnet_id': subnet_id
            }
        }
        if weight:
            member_body['member']['weight'] = weight
        # Allow time before a member fails to create
        for _ in range(30):
            try:
                # Create a member
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.create_lbaas_member(pool['pool']['id'], member_body)
                logging.debug('Added member %s to pool %s', instance_ip, pool['pool']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The member has failed to create
        logging.error('Failed to add member %s', instance_ip)
        return False

    def delete_member(self, member_id, pool_id=None):
        pool = self.get(pool_id)
        # Allow 10 seconds before a member fails to delete
        for _ in range(10):
            try:
                # Delete a member
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_lbaas_member(member_id, pool['pool']['id'])
                logging.debug('Deleted loadbalancer member %s from pool %s',
                              member_id, pool['pool']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The member has failed to delete
        logging.error('Failed to delete loadbalancer member %s from pool %s',
                      member_id, pool['pool']['id'])
        return False

    def delete_members(self, pool_id=None):
        pool = self.get(pool_id)
        members = self.list_members(pool['pool']['id'])
        for member in members:
            self.delete_member(member, pool['pool']['id'])
        logging.debug('Deleted ALL members from pool %s', pool['pool']['id'])

    def load(self, pool_id):
        self.pool = self.neutron.show_lbaas_pool(pool_id)

    def list(self, project_id=None, all_projects=False):
        pool_info = []
        pools = self.neutron.list_lbaas_pools()['pools']
        for pool in pools:
            if not all_projects and project_id and pool['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and pool['tenant_id'] != self.session.get_project_id():
                continue
            pool_info.append({
                'id': pool['id'],
                'name': pool['name']
            })
        return pool_info

    def list_members(self, pool_id=None):
        pool = self.get(pool_id)
        member_info = []
        for member in pool['pool']['members']:
            member_info.append(member['id'])
        return member_info

    def get(self, pool_id=None, use_cached=False):
        if pool_id:
            return self.neutron.show_lbaas_pool(pool_id)
        try:
            if use_cached:
                return self.pool
            return self.neutron.show_lbaas_pool(self.get_id())
        except AttributeError:
            raise OSNetworkError('No pool supplied and no cached pool')

    def get_member(self, member_id, pool_id=None):
        pool = self.get(pool_id)
        return self.neutron.show_lbaas_member(member_id, pool['pool']['id'])

    def get_name(self, pool_id=None, use_cached=False):
        pool = self.get(pool_id, use_cached)
        return pool['pool']['name']

    def get_id(self):
        pool = self.get(use_cached=True)
        return pool['pool']['id']


class lbaasMonitor(BaseNetwork):

    def create(self, pool_id, monitor_type, delay=5, timeout=5, max_retries=3,
               http_method='GET', url_path='/', expected_codes='200'):
        monitor_type = monitor_type.upper()
        if monitor_type not in ['PING', 'TCP', 'HTTP', 'HTTPS']:
            raise OSNetworkError('%s is not a valid monitor type. Must be PING, TCP, HTTP, or HTTPS' % monitor_type)
        monitor_body = {
            'healthmonitor': {
                'pool_id': pool_id,
                'type': monitor_type,
                'delay': delay,
                'timeout': timeout,
                'max_retries': max_retries
            }
        }
        if monitor_type in ['HTTP', 'HTTPS']:
            if not url_path or url_path[0] != '/':
                raise OSNetworkError('Monitor type %s requires a URL path starting with \'/\'' % monitor_type)
            monitor_body['healthmonitor']['http_method'] = http_method
            monitor_body['healthmonitor']['url_path'] = url_path
            monitor_body['healthmonitor']['expected_codes'] = expected_codes
        # Allow time before a health monitor fails to create
        for _ in range(30):
            try:
                # Create a health monitor
                # This may throw an exception, ignore it and wait 1 second
                self.monitor = self.neutron.create_lbaas_healthmonitor(monitor_body)
                logging.debug('Creating loadbalancer health monitor %s under pool %s',
                              self.get_id(), pool_id)
                return True
            except Exception:
                time.sleep(1)
        # The health monitor has failed to create
        logging.error('Failed to create loadbalancer health monitor')
        return False

    def delete(self, monitor_id=None):
        monitor = self.get(monitor_id)
        # Allow 10 seconds before a monitor fails to delete
        for _ in range(10):
            try:
                # Delete a monitor
                # This may throw an exception, ignore it and wait 1 second
                self.neutron.delete_lbaas_healthmonitor(monitor['healthmonitor']['id'])
                logging.debug('Deleted loadbalancer monitor %s', monitor['healthmonitor']['id'])
                return True
            except Exception:
                time.sleep(1)
        # The monitor has failed to delete
        logging.error('Failed to delete loadbalancer monitor %s', monitor['healthmonitor']['id'])
        return False

    def load_monitor(self, monitor_id):
        self.monitor = self.neutron.show_lbaas_healthmonitor(monitor_id)

    def list(self, project_id=None, all_projects=False):
        monitor_info = []
        monitors = self.neutron.list_lbaas_healthmonitors()['healthmonitors']
        for monitor in monitors:
            if not all_projects and project_id and monitor['tenant_id'] != project_id:
                continue
            if not all_projects and not project_id and monitor['tenant_id'] != self.session.get_project_id():
                continue
            monitor_info.append(monitor['id'])
        return monitor_info

    def get(self, monitor_id=None, use_cached=False):
        if monitor_id:
            return self.neutron.show_lbaas_healthmonitor(monitor_id)
        try:
            if use_cached:
                return self.monitor
            return self.neutron.show_lbaas_healthmonitor(self.get_id())
        except AttributeError:
            raise OSNetworkError('No monitor supplied and no cached monitor')

    def get_id(self):
        monitor = self.get(use_cached=True)
        return monitor['healthmonitor']['id']


class Quota(BaseNetwork):

    def get(self, project_id):
        return self.neutron.show_quota(tenant_id=project_id)['quota']


class OSNetworkError(Exception):

    def __init__(self, message):
        super(OSNetworkError, self).__init__(message)
        self.message = message
