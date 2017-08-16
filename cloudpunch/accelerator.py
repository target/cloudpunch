import random
import logging
import threading
import sys
import os
import requests
import json
import yaml
import time
import re

import glanceclient.exc

from tabulate import tabulate
from concurrent.futures import ThreadPoolExecutor
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from cloudpunch import cleanup
from cloudpunch import configuration
from cloudpunch.ostlib import osuser
from cloudpunch.ostlib import osnetwork
from cloudpunch.ostlib import oscompute
from cloudpunch.ostlib import osvolume
from cloudpunch.ostlib import osimage


class Accelerator(object):

    def __init__(self, config, creds, env, admin_mode=False, manual_mode=False,
                 reuse_mode=False, yaml_mode=False, verify=True):
        # Save all arguments
        self.config = config.get_config()
        self.creds = creds
        self.env = env
        self.admin_mode = admin_mode
        self.manual_mode = manual_mode
        self.reuse_mode = reuse_mode
        self.yaml_mode = yaml_mode
        self.verify = verify

        # Randomized ID used to identify the resources created by a run
        self.cp_id = random.randint(1000000, 9999999)
        # Base name for all resources
        self.cp_name = 'cloudpunch-%s' % self.cp_id
        # Randomized password for created user when admin mode is enabled
        self.cp_password = str(random.getrandbits(64))

        # Contains instance information
        self.instance_map = []

        # Stores keystone sessions
        self.sessions = {}

        # Stores external networks
        self.ext_networks = {
            'env1': None,
            'env2': None
        }

        # Stores image ids (because we allow image names)
        self.images = {
            'env1': None,
            'env2': None
        }

        # Resource lists. All resources created are saved in their respective list
        # These are mainly used when cleaning up resources
        self.resources = {}
        for name in ['projects', 'users',
                     'networks', 'routers', 'floaters',
                     'instances', 'volumes', 'keypairs', 'secgroups',
                     'pools', 'pool_vips', 'members', 'monitors',
                     'lbaas_lbs', 'lbaas_pools', 'lbaas_listeners', 'lbaas_monitors'
                     ]:
            if name == 'networks':
                self.resources[name] = {
                    'master': [],
                    'server': [],
                    'client': []
                }
            else:
                self.resources[name] = {
                    'env1': [],
                    'env2': []
                }

        # Information to connect to the master instance
        self.master_ip = None
        self.master_url = None

        # Increases when reuse mode runs another test
        self.test_number = 1

        # Used when a flavor file is enabled
        self.current_flavor = 0
        self.current_percent = 0

        # Used to catch exceptions when running ThreadPoolExecutor
        self.exc_info = None

        # Hide warnings about making insecure connections
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def run(self):
        try:
            # Setup all resources
            self.stage_environment()
            # Handles waiting for the master and slave registration
            self.connect_to_master()
            # Sends the configuration to the master and tells it to start the test
            # It calls post_results() to make it repeatable
            self.run_test()
        except (CPError, oscompute.OSComputeError, osnetwork.OSNetworkError,
                osuser.OSUserError, osvolume.OSVolumeError) as e:
            logging.error(e.message)
        except CPStop as e:
            logging.info(e.message)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logging.error('%s: %s', type(e).__name__, e.message)
        finally:
            # Attempts to remove all resources. Any left over will be saved to a file for later removal
            self.cleanup()

    def stage_environment(self):
        logging.info('Staging environment(s) using ID %s', self.cp_id)

        # env2 is only used in split mode
        labels = ['env1']
        if self.creds['env2']:
            labels.append('env2')
        # Run the stagging process for each environment
        for label in labels:
            logging.info('Staging environment on %s under region %s',
                         self.creds[label].get_creds()['auth_url'],
                         self.creds[label].get_creds()['region_name'])
            # Create the Keystone session
            self.sessions[label] = osuser.Session(self.creds[label], verify=self.verify).get_session()
            # Setup user and project (if admin mode), security group. and keypair
            self.setup_environment(label)
            # Find the external network
            self.ext_networks[label] = osnetwork.ExtNetwork(self.sessions[label],
                                                            self.creds[label].get_region(),
                                                            self.env[label]['api_versions']['neutron'])
            self.ext_networks[label].find_ext_network(self.env[label]['external_network'])
            logging.info('Attaching instances to external network %s with ID %s',
                         self.ext_networks[label].get_name(), self.ext_networks[label].get_id())
            # Find image IDs
            image = osimage.Image(self.sessions[label],
                                  self.creds[label].get_region(),
                                  self.env[label]['api_versions']['glance'])
            try:
                # If image_name is a UUID
                self.images[label] = image.get_name(self.env[label]['image_name'])
            except glanceclient.exc.HTTPNotFound:
                # If image_name is a name
                self.images[label] = image.get_id(self.env[label]['image_name'])
            logging.info('Booting instances using image %s with ID %s',
                         image.get_name(self.images[label]), self.images[label])
            # When split mode is enabled env1 contains the master and servers, env2 contains the clients
            # When disabled, env1 contains everything
            if label == 'env1':
                self.create_master(label)
                roles = ['server']
                if self.config['server_client_mode'] and not self.creds['env2']:
                    roles.append('client')
            else:
                roles = ['client']
            # Setup routers, networks, and subnets
            self.stage_network(roles, label)
            # Setup instances
            self.stage_instances(roles, label)
            # Setup loadbalancers
            self.stage_loadbalancers(roles, label)

        logging.info('Staging complete')
        # Print a table containing hostname, internal IP, and floating IP
        self.show_environment()

    def setup_environment(self, label):
        # Create a project and a user if admin mode is enabled
        if self.admin_mode:
            logging.info('Admin mode enabled, creating own project and user')
            # Create project
            project = osuser.Project(self.sessions[label], self.creds[label].get_region(),
                                     self.creds[label].get_version())
            project.create(self.cp_name)
            self.resources['projects'][label].append(project)
            # Create user
            user = osuser.User(self.sessions[label], self.creds[label].get_region(),
                               self.creds[label].get_version())
            user.create(self.cp_name, self.cp_password, project.get_id())
            self.resources['users'][label].append(user)
            # Change to new user and project
            self.creds[label].change_user(self.cp_name, self.cp_password, self.cp_name)

        # Create security group and add rules based on config
        logging.info('Creating security group')
        secgroup = osnetwork.SecurityGroup(self.sessions[label], self.creds[label].get_region(),
                                           self.env[label]['api_versions']['nova'])
        secgroup.create(self.cp_name)
        for rule in self.env[label]['secgroup_rules']:
            secgroup.add_rule(rule[0], rule[1], rule[2])
        self.resources['secgroups'][label].append(secgroup)

        # Create keypair using public key from config
        logging.info('Creating keypair')
        keypair = oscompute.KeyPair(self.sessions[label], self.creds[label].get_region(),
                                    self.env[label]['api_versions']['nova'])
        keypair.create(self.cp_name, self.env[label]['public_key_file'])
        self.resources['keypairs'][label].append(keypair)

    def create_master(self, label):
        # Resources related to the master will have master in the name
        master_name = '%s-master' % self.cp_name

        # Router
        logging.info('Creating master router')
        router = osnetwork.Router(self.sessions[label], self.creds[label].get_region(),
                                  self.env[label]['api_versions']['neutron'])
        router.create(master_name, self.ext_networks[label].get_id())
        self.resources['routers'][label].append(router)

        # Network
        logging.info('Creating master network')
        network = osnetwork.Network(self.sessions[label], self.creds[label].get_region(),
                                    self.env[label]['api_versions']['neutron'])
        network.create(master_name)
        self.resources['networks']['master'].append(network)

        # Subnet
        subnet = osnetwork.Subnet(self.sessions[label], self.creds[label].get_region(),
                                  self.env[label]['api_versions']['neutron'])
        subnet.create(master_name, self.generate_cidr(), network.get_id(), self.env[label]['dns_nameservers'])
        router.attach_subnet(subnet.get_id())

        # Instance
        logging.info('Creating master instance')
        master_userdata = []
        if type(self.env[label]['shared_userdata']) == list:
            master_userdata.extend(self.env[label]['shared_userdata'])
        if type(self.env[label]['master']['userdata']) == list:
            master_userdata.extend(self.env[label]['master']['userdata'])
        # Hard code command to run the master software
        master_userdata.append('cloudpunch master --debug')
        instance = oscompute.Instance(self.sessions[label], self.creds[label].get_region(),
                                      self.env[label]['api_versions']['nova'])
        instance.create(master_name,
                        self.images[label],
                        self.env[label]['master']['flavor'],
                        network.get_id(),
                        self.env[label]['master']['availability_zone'],
                        self.resources['keypairs'][label][0].get_name(),
                        self.resources['secgroups'][label][0].get_id(),
                        self.config['retry_count'],
                        master_userdata)
        self.resources['instances'][label].append(instance)

        # Attach floater
        floater = osnetwork.FloatingIP(self.sessions[label], self.creds[label].get_region(),
                                       self.env[label]['api_versions']['neutron'])
        floater.create(self.ext_networks[label].get_id())
        self.resources['floaters'][label].append(floater)
        instance.add_float(floater.get_ip())

        # Save information to connect to master
        master_ips = instance.list_ips(include_networks=False)
        self.master_ip = master_ips['fixed'][0]
        if self.config['network_mode'] == 'full':
            self.master_ip = master_ips['floating'][0]
        self.master_url = 'http://%s' % master_ips['floating'][0]

    def stage_network(self, roles, label):
        # Setup environment when network_mode is full
        if self.config['network_mode'] == 'full':
            for role in roles:
                # Create number of routers based on config
                for router_num in range(self.config['number_routers']):
                    router_num += 1
                    logging.info('Creating %s router %s of %s',
                                 role, router_num, self.config['number_routers'])
                    router = osnetwork.Router(self.sessions[label], self.creds[label].get_region(),
                                              self.env[label]['api_versions']['neutron'])
                    router.create('%s-%s-r%s' % (self.cp_name, role[0], router_num),
                                  self.ext_networks[label].get_id())
                    self.resources['routers'][label].append(router)

                    # Create number of networks per router based on config
                    for network_num in range(self.config['networks_per_router']):
                        network_num += 1
                        logging.info('Creating %s network %s of %s on router %s',
                                     role, network_num, self.config['networks_per_router'], router_num)
                        network = osnetwork.Network(self.sessions[label], self.creds[label].get_region(),
                                                    self.env[label]['api_versions']['neutron'])
                        network.create('%s-%s-r%s-n%s' % (self.cp_name, role[0], router_num, network_num))
                        self.resources['networks'][role].append(network)

                        # Create subnet for this network and attach to router
                        subnet = osnetwork.Subnet(self.sessions[label], self.creds[label].get_region(),
                                                  self.env[label]['api_versions']['neutron'])
                        subnet.create('%s-%s-r%s-n%s' % (self.cp_name, role[0], router_num, network_num),
                                      self.generate_cidr(role, router_num, network_num),
                                      network.get_id(), self.env[label]['dns_nameservers'])
                        router.attach_subnet(subnet.get_id())

        # Setup environment when network_mode is single-router
        elif self.config['network_mode'] == 'single-router':
            for role in roles:
                # Create number of networks based on config
                # These networks connect to the master router
                for network_num in range(self.config['networks_per_router']):
                    network_num += 1
                    logging.info('Creating %s network %s of %s on master router',
                                 role, network_num, self.config['networks_per_router'])
                    network = osnetwork.Network(self.sessions[label], self.creds[label].get_region(),
                                                self.env[label]['api_versions']['neutron'])
                    network.create('%s-%s-master-n%s' % (self.cp_name, role[0], network_num))
                    self.resources['networks'][role].append(network)

                    # Create subnet for this network and attach to router
                    subnet = osnetwork.Subnet(self.sessions[label], self.creds[label].get_region(),
                                              self.env[label]['api_versions']['neutron'])
                    subnet.create('%s-%s-master-n%s' % (self.cp_name, role[0], network_num),
                                  self.generate_cidr(role=role, network_num=network_num),
                                  network.get_id(), self.env[label]['dns_nameservers'])
                    self.resources['routers'][label][0].attach_subnet(subnet.get_id())

        # single-network does not require a network setup

    def stage_instances(self, roles, label):
        # Create list of instance data
        instance_map = self.create_instance_map(roles, label)

        # Start thread to create instances
        thread = threading.Thread(target=self.create_instances,
                                  args=[self.config['instance_threads'], instance_map])
        thread.daemon = True
        thread.start()
        thread.join()

        # Catches any exceptions
        if self.exc_info:
            raise self.exc_info[1], None, self.exc_info[2]

    def create_instance_map(self, roles, label):
        instance_map = []
        for role in roles:
            # network_mode full and single-router do not use the master network
            # network_mode single-network uses the the master
            if self.config['network_mode'] == 'single-network':
                networks = self.resources['networks']['master']
            else:
                networks = self.resources['networks'][role]

            # Setup flavor file to start at beginning
            if 'flavor_file' in self.config:
                current_flavor = 0
                current_percent = float(self.config['flavor_file'][self.config['flavor_file'].keys()[0]])

            # The number of instances is directly related to the number of networks
            for network in networks:
                # Create number of instances based on config
                for instance_num in range(self.config['instances_per_network']):
                    # Generate instance information
                    instance = {
                        'name': '%s-%s%s' % (network.get_name(), role[0], instance_num + 1),
                        'network': network,
                        'role': role,
                        'keypair': self.resources['keypairs'][label][0],
                        'secgroup': self.resources['secgroups'][label][0]
                    }

                    # Flavor file determines the flavor based on percentage
                    if 'flavor_file' in self.config:
                        # Get the instance's number
                        inst_num = self.get_instance_num(instance['name'])
                        # All the possible flavors
                        keys = self.config['flavor_file'].keys()
                        # Percent of the instance number compared to the total instances
                        percent = float(inst_num) / float(self.get_total_instance_num()) * 100.0
                        # The percent is within the current flavor
                        if percent <= current_percent or percent >= 99.0:
                            flavor = keys[current_flavor]
                        # Otherwise move onto the next flavor and add it's percent
                        else:
                            current_flavor += 1
                            current_percent += float(self.config['flavor_file'][keys[current_flavor]])
                            flavor = keys[current_flavor]
                    # Use the flavor specified in the config if there is no flavor file
                    else:
                        flavor = self.env[label][role]['flavor']
                    instance['flavor'] = flavor
                    instance_map.append(instance)

        # Add this run's instance map to the current instance map
        self.instance_map = list(self.instance_map) + instance_map
        return instance_map

    def create_instances(self, threads, instance_map):
        logging.info('Creating instances')
        try:
            # Start the instance creation process on OpenStack
            # ThreadPoolExecutor is used to have a specific number of instances creating at a time
            thread_exec = ThreadPoolExecutor(max_workers=threads)
            # This is used to catch exceptions
            for result in thread_exec.map(self.create_instance, instance_map):
                pass
            # Make all threads finish before continuing
            thread_exec.shutdown(wait=True)
        except Exception:
            # Used to send back exceptions
            self.exc_info = sys.exc_info()

    def create_instance(self, instance_map):
        logging.info('Creating instance %s', instance_map['name'])

        # Figure out current environment
        if self.creds['env2'] and instance_map['role'] == 'client':
            label = 'env2'
        else:
            label = 'env1'

        slave_userdata = []
        if type(self.env[label]['shared_userdata']) == list:
            slave_userdata.extend(self.env[label]['shared_userdata'])
        if type(self.env[label][instance_map['role']]['userdata']) == list:
            slave_userdata.extend(self.env[label][instance_map['role']]['userdata'])
        # Hard code command to run the slave software
        slave_userdata.append('cloudpunch slave %s' % self.master_ip)

        # Find out availability zone if there is a hostmap file
        if 'hostmap' in self.config:
            # Get the instance's number
            instance_num = self.get_instance_num(instance_map['name'])
            # Figure out the instance's zone should be based on it's number
            hostmap = self.get_hostmap(instance_num)
            # Assign it the one left of the ',' if server, the right one if client
            hostmap = hostmap.split(',')
            avail_zone = hostmap[0] if instance_map['role'] == 'server' else hostmap[1]
        # Otherwise just use the config
        else:
            avail_zone = self.env[label][instance_map['role']]['availability_zone']

        # Boot from volume if enabled
        vol_boot = None
        if 'boot_from_vol' in self.env[label][instance_map['role']]:
            if self.env[label][instance_map['role']]['boot_from_vol']['enable']:
                vol_boot = self.env[label][instance_map['role']]['boot_from_vol']['size']

        # Create the instance using information from the instance_map
        instance = oscompute.Instance(self.sessions[label], self.creds[label].get_region(),
                                      self.env[label]['api_versions']['nova'])
        instance.create(instance_map['name'],
                        self.images[label],
                        instance_map['flavor'],
                        instance_map['network'].get_id(),
                        avail_zone,
                        instance_map['keypair'].get_name(),
                        instance_map['secgroup'].get_id(),
                        self.config['retry_count'],
                        user_data=slave_userdata,
                        boot_from_vol=vol_boot)
        self.resources['instances'][label].append(instance)

        # Create a volume if configuration has it enabled
        if ('volume' in self.env[label][instance_map['role']] and
                self.env[label][instance_map['role']]['volume']['enable']):
            # Check if volume exists. Recovery mode does not delete volume
            skip_creation = False
            for v in self.resources['volumes'][label]:
                if v.get_name() == instance_map['name']:
                    skip_creation = True
                    volume = v
                    break
            # Create cinder volume
            if not skip_creation:
                volume = osvolume.Volume(self.sessions[label], self.creds[label].get_region(),
                                         self.env[label]['api_versions']['cinder'])
                volume.create(self.env[label][instance_map['role']]['volume']['size'],
                              instance_map['name'],
                              volume_type=self.env[label][instance_map['role']]['volume']['type'],
                              availability_zone=self.env[label][instance_map['role']]['volume']['availability_zone'])
                self.resources['volumes'][label].append(volume)

            # Attach volume to instance
            instance.attach_volume(volume.get_id())

        # Only network_mode full puts floating IP addresses on slaves
        if self.config['network_mode'] == 'full':
            # Allocate a floating IP address
            floater = osnetwork.FloatingIP(self.sessions[label], self.creds[label].get_region(),
                                           self.env[label]['api_versions']['neutron'])
            floater.create(self.ext_networks[label].get_id())
            self.resources['floaters'][label].append(floater)

            # Assign floating IP address to instance
            instance.add_float(floater.get_ip())

    def get_instance_num(self, instance_name):
        # Split the name to find relevant information
        instance_name_split = instance_name.split('-')
        # network_mode full looks at router, network, and instance number
        if self.config['network_mode'] == 'full':
            # How this works...
            # Given the hostname cloudpunch-9079364-c-r1-n2-c1
            # With the setup 2 routers, 2 networks per router, 2 instances per network
            # The order of creation is:
                # cloudpunch-9079364-c-r1-n1-c1
                # cloudpunch-9079364-c-r1-n1-c2
                # cloudpunch-9079364-c-r1-n2-c1 <-
                # cloudpunch-9079364-c-r1-n2-c2
                # cloudpunch-9079364-c-r2-n1-c1
                # cloudpunch-9079364-c-r2-n1-c2
                # ...
            # My router number is 1
            rtr_num = int(instance_name_split[3][1:])
            # My network number is 2
            net_num = int(instance_name_split[4][1:])
            # My instance number is 1
            inst_num = int(instance_name_split[5][1:])
            # The first number is taking into account the number of instances before this router
            # In this case there is none because router number is 1
            first_num = (rtr_num - 1) * self.config['networks_per_router'] * self.config['instances_per_network']
            # The second number is taking into account the number of instances before this network on this router
            # In this case there were 2 instances before this one on this router
            second_num = (net_num - 1) * self.config['instances_per_network']
            # Add these numbers together with the instance number
            return first_num + second_num + inst_num
            # Getting a result of 3
        elif self.config['network_mode'] == 'single-router':
            # Same as above but not taking into account the number of routers
            net_num = int(instance_name_split[4][1:])
            inst_num = int(instance_name_split[5][1:])
            second_num = (net_num - 1) * self.config['instances_per_network']
            return second_num + inst_num
        elif self.config['network_mode'] == 'single-network':
            # Same as above but not taking into account the number of routers or networks
            return int(instance_name_split[3][1:])

    def get_total_instance_num(self):
        # Start with the number of instances per network
        total = self.config['instances_per_network']
        # network_mode single-router and full have multiple networks
        if self.config['network_mode'] in ['single-router', 'full']:
            total = total * self.config['networks_per_router']
        # network_mode full has multiple routers
        if self.config['network_mode'] == 'full':
            total = total * self.config['router_num']
        return total

    def get_hostmap(self, instance_num):
        # Use the % operator to find left over because the hostmap is looped through
        # For example: the hostmap has 5 entries, the current instance_num is 6, line 1 will be used
        line = instance_num % len(self.config['hostmap']['map'])
        # If there is no leftover, it's the last entry
        if line == 0:
            line = len(self.config['hostmap']['map'])
        # Adjust for index 0
        hostmap = self.config['hostmap']['map'][line - 1]
        hostmap_split = hostmap.split(',')
        # Replace hostmap entries with tag if it exists
        for host in hostmap_split:
            if host in self.config['hostmap']['tags']:
                hostmap = hostmap.replace(host, self.config['hostmap']['tags'][host])
        return hostmap

    def generate_cidr(self, role='server', router_num=0, network_num=0):
        # To keep network address generation simple, they are generated inside octets
        # The master subet uses 10.0.0.0
        # Client networks start at 128
        if self.config['network_mode'] == 'full':
            if role == 'client':
                router_num += 127
            return '10.%s.%s.0/24' % (router_num, network_num)
        elif self.config['network_mode'] == 'single-router':
            if role == 'client':
                network_num += 127
            return '10.%s.0.0/16' % (network_num)
        elif self.config['network_mode'] == 'single-network':
            return '10.0.0.0/16'

    def stage_loadbalancers(self, roles, label):
        for role in roles:
            if 'loadbalancer' not in self.env[label][role] or not self.env[label][role]['loadbalancer']['enable']:
                continue
            if 'loadbalancers' not in self.config:
                self.config['loadbalancers'] = {}
            if self.config['network_mode'] == 'single-network':
                lb_list = [None] * len(self.resources['networks']['master'])
                networks = self.resources['networks']['master']
            else:
                lb_list = [None] * len(self.resources['networks'][role])
                networks = self.resources['networks'][role]
            for network in networks:
                if self.config['network_mode'] == 'single-network':
                    name = '%s-master-%s' % (self.cp_name, role[0])
                else:
                    name = network.get_name()
                subnet_id = network.list_subnets()[0]
                logging.info('Creating loadbalancer %s', name)

                if self.env[label]['api_versions']['lbaas'] == 1:
                    pool = osnetwork.Pool(self.sessions[label], self.creds[label].get_region(),
                                          self.env[label]['api_versions']['neutron'])
                    pool.create(name,
                                self.env[label][role]['loadbalancer']['method'],
                                self.env[label][role]['loadbalancer']['backend']['protocol'],
                                subnet_id)
                    self.resources['pools'][label].append(pool)

                    pool_vip = osnetwork.PoolVIP(self.sessions[label], self.creds[label].get_region(),
                                                 self.env[label]['api_versions']['neutron'])
                    pool_vip.create(name,
                                    self.env[label][role]['loadbalancer']['frontend']['port'],
                                    self.env[label][role]['loadbalancer']['frontend']['protocol'],
                                    subnet_id,
                                    pool.get_id())
                    self.resources['pool_vips'][label].append(pool_vip)
                    if self.config['network_mode'] == 'full':
                        floater = osnetwork.FloatingIP(self.sessions[label], self.creds[label].get_region(),
                                                       self.env[label]['api_versions']['neutron'])
                        floater.create(self.ext_networks[label].get_id(), pool_vip.get_vip_port())
                        self.resources['floaters'][label].append(floater)
                        lb_list[self.get_network_num(name) - 1] = floater.get_ip()
                    else:
                        lb_list[self.get_network_num(name) - 1] = pool_vip.get_vip_address()

                    instances_on_network = filter(lambda x: x['network'] == network and x['role'] == role,
                                                  self.instance_map)
                    for instance in instances_on_network:
                        instance_object = filter(lambda x: x.get_name() == instance['name'],
                                                 self.resources['instances'][label])[0]
                        fixed_ip = instance_object.list_ips(include_networks=False)['fixed'][0]
                        member = osnetwork.Member(self.sessions[label], self.creds[label].get_region(),
                                                  self.env[label]['api_versions']['neutron'])
                        member.create(fixed_ip, pool.get_id(),
                                      self.env[label][role]['loadbalancer']['backend']['port'])
                        self.resources['members'][label].append(member)

                    monitor = osnetwork.Monitor(self.sessions[label], self.creds[label].get_region(),
                                                self.env[label]['api_versions']['neutron'])
                    monitor.create(self.env[label][role]['loadbalancer']['healthmonitor']['type'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['delay'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['timeout'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['retries'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['http_method'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['url_path'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['expected_codes'])
                    self.resources['monitors'][label].append(monitor)

                    pool.associate_monitor(monitor.get_id())

                elif self.env[label]['api_versions']['lbaas'] == 2:
                    lb = osnetwork.lbaasLB(self.sessions[label], self.creds[label].get_region(),
                                           self.env[label]['api_versions']['neutron'])
                    lb.create(name, subnet_id)
                    self.resources['lbaas_lbs'][label].append(lb)
                    if self.config['network_mode'] == 'full':
                        floater = osnetwork.FloatingIP(self.sessions[label], self.creds[label].get_region(),
                                                       self.env[label]['api_versions']['neutron'])
                        floater.create(self.ext_networks[label].get_id(), lb.get_vip_port())
                        self.resources['floaters'][label].append(floater)
                        lb_list[self.get_network_num(name) - 1] = floater.get_ip()
                    else:
                        lb_list[self.get_network_num(name) - 1] = lb.get_vip_address()

                    pool = osnetwork.lbaasPool(self.sessions[label], self.creds[label].get_region(),
                                               self.env[label]['api_versions']['neutron'])
                    pool.create(name, self.env[label][role]['loadbalancer']['method'],
                                self.env[label][role]['loadbalancer']['backend']['protocol'], lb.get_id())
                    self.resources['lbaas_pools'][label].append(pool)

                    listener = osnetwork.lbaasListener(self.sessions[label], self.creds[label].get_region(),
                                                       self.env[label]['api_versions']['neutron'])
                    listener.create(name, lb.get_id(), pool.get_id(),
                                    self.env[label][role]['loadbalancer']['frontend']['protocol'],
                                    self.env[label][role]['loadbalancer']['frontend']['port'])
                    self.resources['lbaas_listeners'][label].append(listener)

                    instances_on_network = filter(lambda x: x['network'] == network and x['role'] == role,
                                                  self.instance_map)
                    for instance in instances_on_network:
                        instance_object = filter(lambda x: x.get_name() == instance['name'],
                                                 self.resources['instances'][label])[0]
                        fixed_ip = instance_object.list_ips(include_networks=False)['fixed'][0]
                        pool.add_member(fixed_ip,
                                        self.env[label][role]['loadbalancer']['backend']['port'],
                                        subnet_id)

                    monitor = osnetwork.lbaasMonitor(self.sessions[label], self.creds[label].get_region(),
                                                     self.env[label]['api_versions']['neutron'])
                    monitor.create(pool.get_id(),
                                   self.env[label][role]['loadbalancer']['healthmonitor']['type'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['delay'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['timeout'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['retries'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['http_method'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['url_path'],
                                   self.env[label][role]['loadbalancer']['healthmonitor']['expected_codes'])
                    self.resources['lbaas_monitors'][label].append(monitor)
            self.config['loadbalancers'][role] = lb_list

    def get_network_num(self, network_name):
        if self.config['network_mode'] == 'single-network':
            return 1
        network_name_split = network_name.split('-')
        if self.config['network_mode'] == 'full':
            # cloudpunch-9079364-c-r1-n1
            router_num = int(network_name_split[3][1:])
            network_num = int(network_name_split[4][1:])
            first_num = (router_num - 1) * self.config['networks_per_router']
            return first_num + network_num
        elif self.config['network_mode'] == 'single-router':
            # cloudpunch-9079364-c-master-n1
            return int(network_name_split[4][1:])

    def show_environment(self):
        # Creates a table to show instance information
        table = [['Instance Name', 'Fixed IP', 'Floating IP']]
        for label in ['env1', 'env2']:
            for instance in self.resources['instances'][label]:
                # index 0 is always the instance's private IP
                # index 1 is always the instance's floating IP
                ips = instance.list_ips(include_networks=False)
                floating_ip = ips['floating'][0] if ips['floating'] else '-'
                row = [instance.get_name(), ips['fixed'][0], floating_ip]
                table.append(row)
        logging.info('Environment Details\n%s',
                     tabulate(table, headers='firstrow', tablefmt='psql'))

    def connect_to_master(self):
        # Wait for master server to be ready
        status = 0
        for num in range(self.config['retry_count']):
            logging.info('Attempting to connect to master instance. Retry %s of %s',
                         num + 1, self.config['retry_count'])
            try:
                request = requests.get('%s/api/system/health' % self.master_url, timeout=3)
                status = request.status_code
            except requests.exceptions.RequestException:
                status = 0
            if status == 200:
                logging.info('Connected successfully to master instance')
                break
            time.sleep(5)
        if status != 200:
            raise CPError('Unable to connect to master instance. Aborting')

        # Wait for all servers to register to master server
        registered_servers = 0
        total_servers = len(self.resources['instances']['env1']) + len(self.resources['instances']['env2']) - 1
        for num in range(self.config['retry_count']):
            logging.info('Waiting for all instances to register. %s of %s registered. Retry %s of %s',
                         registered_servers, total_servers, num + 1, self.config['retry_count'])
            try:
                request = requests.get('%s/api/register' % self.master_url, timeout=3)
                response = json.loads(request.text)
                registered_servers = response['count']
                if registered_servers == total_servers:
                    logging.info('All instances registered')
                    break

                # Start recovery process if enabled and hit number of retries
                if self.config['recovery']['enable'] and (num + 1) == self.config['recovery']['retries']:
                    logging.info('Recovery mode enabled and number of retries has been hit')
                    percent_registered = float(registered_servers) / float(total_servers) * 100
                    threshold = float(self.config['recovery']['threshold'])
                    # Continue process if passed threshold
                    if percent_registered >= threshold:
                        logging.info('Percent registered (%s%%) is pass recovery threshold (%s%%)',
                                     percent_registered, threshold)
                        response = self.start_recovery(total_servers)
                        if response == 'abort':
                            # Set to all registered as to not say all instances are not registered
                            registered_servers = total_servers
                            break
                    else:
                        logging.info('Percent registered (%s%%) does not pass recovery threshold (%s%%).'
                                     ' Not attempting recovery',
                                     percent_registered, threshold)

            except requests.exceptions.RequestException:
                logging.info('Failed connection to master instance, trying again')
            time.sleep(5)
        if registered_servers != total_servers:
            raise CPError('Not all instances registered. Aborting')

    def start_recovery(self, total_servers):
        if self.config['recovery']['type'] == 'ask':
            # User can enter the full word or just the first letter
            regex = '^(r(ebuild)?|a(bort)?|i(gnore)?)$'
            recovery_type = raw_input('Enter recovery type (rebuild, abort, ignore) ')
            match = re.search(regex, recovery_type)
            while not match:
                print('Not a valid recovery type')
                recovery_type = raw_input('Enter recovery type (rebuild, abort, ignore) ')
                match = re.search(regex, recovery_type)
            recovery_type = recovery_type[0]
        else:
            # Get the first letter of the recovery type in configuration
            recovery_type = self.config['recovery']['type'][0]

        # Abort
        if recovery_type == 'a':
            raise CPStop('Recovery mode is abort. Aborting')

        # Rebuild
        elif recovery_type == 'r':
            logging.info('Recovery mode is rebuild. Rebuilding unregistered instances')
            # Get an up to date instance count
            status = 0
            while status != 200:
                try:
                    request = requests.get('%s/api/register' % self.master_url, timeout=3)
                    status = request.status_code
                    response = json.loads(request.text)
                    registered_servers = response['count']
                except (requests.exceptions.RequestException, ValueError):
                    status = 0
                if status != 200:
                    time.sleep(1)
            if registered_servers == total_servers:
                logging.info('All servers registered. Stopping rebuild')
                return 'abort'
            # Get the number of each role that are missing
            logging.info('Rebuilding %s instance(s)', total_servers - len(response['instances']))
            # Delete missing instances
            logging.info('Deleting unregistered instances')
            # Get instance objects so they can be deleted
            instances = self.get_missing_instance_objects(response['instances'])
            for instance in instances:
                instance.detach_volume()
                instance.remove_float()
                instance.delete_instance()
                # Remove them from resource list
                for label in ['env1', 'env2']:
                    try:
                        self.resources['instances'][label].remove(instance)
                    except ValueError:
                        pass
            logging.info('Recreating unregistered instances')
            # Recreate instance map with ones that are missing
            instance_map = self.get_missing_instances(response['instances'])
            # Start instance creation process
            thread = threading.Thread(target=self.create_instances,
                                      args=[self.config['instance_threads'], instance_map])
            thread.daemon = True
            thread.start()
            thread.join()
            # Used to catch exceptions
            if self.exc_info:
                raise self.exc_info[1], None, self.exc_info[2]
            logging.info('Staging complete')
            # Show the environment again
            self.show_environment()
            # Restart registration process
            self.connect_to_master()
            return 'abort'

        # Ignore
        elif recovery_type == 'i':
            logging.info('Ignoring recovery')
            return 'ignore'

    def get_missing_instances(self, instances):
        # Copy the original instance map
        missing_instances = list(self.instance_map)
        for instance in instances:
            for instance_map in self.instance_map:
                # Provided instances are ones that are good. Remove them from new list
                if instance['hostname'] == instance_map['name']:
                    missing_instances.remove(instance_map)
        # This list contains only those instances that have not registered
        return missing_instances

    def get_missing_instance_objects(self, instances):
        # Copy the instance resource list
        missing_instances = list(self.resources['instances']['env1']) + list(self.resources['instances']['env2'])
        for instance_obj in list(self.resources['instances']['env1']) + list(self.resources['instances']['env2']):
            # This is to find the master instance
            if len(instance_obj.get_name().split('-')) == 3:
                missing_instances.remove(instance_obj)
            for instance in instances:
                # Provided instances are ones that are good. Remove them from new list
                if instance['hostname'] == instance_obj.get_name():
                    missing_instances.remove(instance_obj)
        # This list contains only those instances that have not registered
        return missing_instances

    def run_test(self):
        # Send configuration over to master
        status = 0
        for num in range(self.config['retry_count']):
            try:
                request = requests.post('%s/api/config' % self.master_url, json=self.config, timeout=3)
                status = request.status_code
            except requests.exceptions.RequestException:
                status = 0
            if status == 200:
                logging.info('Sent configuration to master')
                break
            logging.info('Failed to send configuration to master. Retry %s of %s',
                         num + 1, self.config['retry_count'])
            time.sleep(1)
        if status != 200:
            raise CPError('Failed to send configuration to master. Aborting')

        # Wait for user input if manual_mode is enabled
        if self.manual_mode:
            raw_input('Press enter to start test')

        logging.info('Starting test')

        # Tell master to match servers and clients
        # This also signals the start of the test
        status = 0
        for num in range(self.config['retry_count']):
            try:
                request = requests.get('%s/api/test/match' % self.master_url, timeout=3)
                status = request.status_code
            except requests.exceptions.RequestException:
                status = 0
            if status == 200:
                logging.info('Signaled master to start test')
                break
            logging.info('Failed to signal master to start test. Retry %s of %s',
                         num + 1, self.config['retry_count'])
            time.sleep(1)
        if status != 200:
            raise CPError('Failed to signal master to start test. Aborting')

        # Wait for tests to finish and get results
        complete_servers = 0
        total_servers = len(self.resources['instances']['env1']) + len(self.resources['instances']['env2']) - 1
        if self.config['server_client_mode'] and not self.config['servers_give_results']:
            total_servers = total_servers / 2
        logging.info('Waiting for results')
        while True:
            logging.info('Checking for complete results. %s of %s instances have posted results',
                         complete_servers, total_servers)
            try:
                request = requests.get('%s/api/test/results' % self.master_url, timeout=3)
                data = json.loads(request.text)
                complete_servers = len(data)
            except (requests.exceptions.RequestException, ValueError):
                pass
            if complete_servers == total_servers:
                logging.info('All instances have posted results')
                break
            time.sleep(5)
        self.post_results()

    def post_results(self):
        # Get results from master instance
        status = 0
        for num in range(self.config['retry_count']):
            try:
                request = requests.get('%s/api/test/results' % self.master_url, timeout=3)
                status = request.status_code
                results = request.text
            except requests.exceptions.RequestException:
                status = 0
            if status == 200:
                logging.info('Got results from master')
                break
            logging.info('Failed to get results from master. Retry %s of %s',
                         num + 1, self.config['retry_count'])
            time.sleep(1)
        if status != 200:
            raise CPError('Failed to get results from master. Aborting')

        # Translate results to YAML if yaml_mode is enabled
        if self.yaml_mode:
            results = yaml.dump(yaml.load(results), default_flow_style=False)

        # Send to file if in configuration or send to stdout
        if 'output_file' in self.config:
            output_file = self.config['output_file']
            # Add a number to tests that have repeated via reuse mode
            if self.test_number > 1:
                output_file = '%s-%s%s' % (os.path.splitext(os.path.basename(output_file))[0],
                                           self.test_number,
                                           os.path.splitext(os.path.basename(output_file))[1])
            logging.info('Saving test results to the file %s' % output_file)
            with open(output_file, 'w') as f:
                f.write(results)
        else:
            logging.info('Results: \n%s' % results)

        # Ask user to start another test if reuse_mode is enabled
        if self.reuse_mode:
            # User can enter the full word or just the first letter
            regex = '^(s(ame)?|d(ifferent)?|a(bort)?)$'
            newtest_type = raw_input('Enter new test type (same, different, abort) ')
            match = re.search(regex, newtest_type)
            while not match:
                print('Not a valid new test type')
                newtest_type = raw_input('Enter new test type (same, different, abort) ')
                match = re.search(regex, newtest_type)
            newtest_type = newtest_type[0]
            # Same
            if newtest_type == 's':
                logging.info('Running the same test')
                self.rerun_test()
            # Different
            elif newtest_type == 'd':
                logging.info('Running a different test')
                # Infinite loop to catch no input and invalid configuration files
                while True:
                    new_config = raw_input('Enter a new configuration file: ')
                    if new_config:
                        try:
                            # Copy over the output file and hostmap file
                            output_file = self.config['output_file'] if 'output_file' in self.config else None
                            hostmap_file = self.config['hostmap_file'] if 'hostmap_file' in self.config else None
                            config = configuration.Configuration(new_config, output_file, hostmap_file)
                            self.config = config.get_config()
                            break
                        # Print out any configuration errors
                        except configuration.ConfigError as e:
                            print(e.message)
                self.rerun_test()
            # Abort
            elif newtest_type == 'a':
                logging.info('Not running another test')

    def rerun_test(self):
        # Tell master to restart the test
        for num in range(self.config['retry_count']):
            try:
                request = requests.delete('%s/api/test/status' % self.master_url, timeout=3)
                status = request.status_code
            except requests.exceptions.RequestException:
                status = 0
            if status == 200:
                logging.info('Signaled master to reset test')
                self.test_number += 1
                break
            logging.info('Failed to signal master to reset test. Retry %s of %s',
                         num + 1, self.config['retry_count'])
            time.sleep(1)
        if status != 200:
            raise CPError('Failed to signal master to reset test. Aborting')
        self.run_test()

    def cleanup(self):
        logging.info('Checking for resources to cleanup')
        labels = ['env1']
        if self.creds['env2']:
            labels.append('env2')

        # Check for resources left on OpenStack
        for label in labels:
            self.check_resources(label)

    def check_resources(self, label):
        cleanup_data = {}

        for resource in self.resources:
            if resource == 'networks':
                continue
            elif self.resources[resource][label]:
                cleanup_data[resource] = []
                for r in self.resources[resource][label]:
                    if resource == 'keypairs':
                        cleanup_data[resource].append(r.get_name())
                    else:
                        cleanup_data[resource].append(r.get_id())

        roles = ['master', 'server', 'client']
        if self.creds['env2']:
            roles = ['master', 'server'] if label == 'env1' else ['client']
        for role in roles:
            if self.resources['networks'][role]:
                name = '%s-network' % role
                cleanup_data[name] = []
                for network in self.resources['networks'][role]:
                    cleanup_data[name].append(network.get_id())

        if cleanup_data:
            # Add OpenStack API versions to cleanup data
            cleanup_data['api_versions'] = self.env[label]['api_versions']
            # The name is based on ID and env
            fname = '%s-%s-cleanup.json' % (self.cp_name, label)
            resource_cleanup = cleanup.Cleanup(self.creds[label],
                                               cleanup_file=fname,
                                               cleanup_data=cleanup_data,
                                               cleanup_resources=self.config['cleanup_resources'],
                                               verify=self.verify)
            resource_cleanup.run()


class CPError(Exception):

    def __init__(self, message):
        super(CPError, self).__init__(message)
        self.message = message


class CPStop(Exception):

    def __init__(self, message):
        super(CPStop, self).__init__(message)
        self.message = message
