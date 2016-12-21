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
import datadog

from tabulate import tabulate
from concurrent.futures import ThreadPoolExecutor
from requests.packages.urllib3.exceptions import InsecureRequestWarning

import configuration
import osuser
import osnetwork
import oscompute
import osvolume


class Accelerator(object):

    def __init__(self, config, creds, env, admin_mode=False, manual_mode=False,
                 reuse_mode=False, yaml_mode=False, insecure_mode=False):
        # Save all arguments
        self.config = config.get_config()
        self.creds = creds
        self.env = env
        self.admin_mode = admin_mode
        self.manual_mode = manual_mode
        self.reuse_mode = reuse_mode
        self.yaml_mode = yaml_mode
        self.insecure_mode = insecure_mode

        # Randomized ID used to identify the resources created by a run
        self.cp_id = random.randint(1000000, 9999999)
        # Base name for all resources
        self.cp_name = 'cloudpunch-%s' % self.cp_id
        # Randomized password for created user when admin mode is enabled
        self.cp_password = str(random.getrandbits(64))

        # Contains instance information
        self.instance_map = []

        # Resource lists. All resources created are saved in their respective list
        # These are mainly used when cleaning up resources
        self.sessions = {}
        self.projects = {
            'env1': [],
            'env2': []
        }
        self.users = {
            'env1': [],
            'env2': []
        }
        self.networks = {
            'master': [],
            'server': [],
            'client': []
        }
        self.routers = {
            'env1': [],
            'env2': []
        }
        self.instances = {
            'env1': [],
            'env2': []
        }
        self.volumes = {
            'env1': [],
            'env2': []
        }
        self.keypairs = {
            'env1': [],
            'env2': []
        }
        self.secgroups = {
            'env1': [],
            'env2': []
        }
        self.floaters = {
            'env1': [],
            'env2': []
        }
        self.ext_network = {
            'env1': None,
            'env2': None
        }

        # Information to connect to the master instance
        self.master_ip = None
        self.master_url = None

        # Used to know if the test started when cleanup() is called
        self.test_started = False
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
            self.sessions[label] = osuser.Session(self.creds[label], verify=self.insecure_mode).get_session()
            # Setup user and project (if admin mode), security group. and keypair
            self.setup_environment(label)
            # Find the external network
            self.ext_network[label] = osnetwork.ExtNetwork(self.sessions[label], self.creds[label].get_region(),
                                                           self.env[label]['api_versions']['neutron'])
            self.ext_network[label].find_ext_network(self.env[label]['external_network'])
            logging.info('Attaching instances to external network %s with ID %s',
                         self.ext_network[label].get_name(), self.ext_network[label].get_id())
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

        # Print a table containing hostname, internal IP, and floating IP
        self.show_environment()

    def setup_environment(self, label):
        # Create a project and a user if admin mode is enabled
        if self.admin_mode:
            logging.info('Admin mode enabled, creating own project and user')
            # Create project
            project = osuser.Project(self.sessions[label], self.creds[label].get_region(),
                                     self.creds[label].get_version())
            project.create_project(self.cp_name)
            self.projects[label].append(project)
            # Create user
            user = osuser.User(self.sessions[label], self.creds[label].get_region(),
                               self.creds[label].get_version())
            user.create_user(self.cp_name, self.cp_password, project.get_id())
            self.users[label].append(user)
            # Change to new user and project
            self.creds[label].change_user(self.cp_name, self.cp_password, self.cp_name)

        # Create security group and add rules based on config
        logging.info('Creating security group')
        secgroup = oscompute.SecGroup(self.sessions[label], self.creds[label].get_region(),
                                      self.env[label]['api_versions']['nova'])
        secgroup.create_secgroup(self.cp_name)
        for rule in self.env[label]['secgroup_rules']:
            secgroup.add_rule(rule[0], rule[1], rule[2])
        self.secgroups[label].append(secgroup)

        # Create keypair using public key from config
        logging.info('Creating keypair')
        keypair = oscompute.KeyPair(self.sessions[label], self.creds[label].get_region(),
                                    self.env[label]['api_versions']['nova'])
        keypair.create_keypair(self.cp_name, self.env[label]['public_key_file'])
        self.keypairs[label].append(keypair)

    def create_master(self, label):
        # Resources related to the master will have master in the name
        master_name = '%s-master' % self.cp_name

        # Router
        logging.info('Creating master router')
        router = osnetwork.Router(self.sessions[label], self.creds[label].get_region(),
                                  self.env[label]['api_versions']['neutron'])
        router.create_router(master_name, self.ext_network[label].get_id())
        self.routers[label].append(router)

        # Network
        logging.info('Creating master network')
        network = osnetwork.Network(self.sessions[label], self.creds[label].get_region(),
                                    self.env[label]['api_versions']['neutron'])
        network.create_network(master_name)
        self.networks['master'].append(network)

        # Subnet
        subnet = osnetwork.Subnet(self.sessions[label], self.creds[label].get_region(),
                                  self.env[label]['api_versions']['neutron'])
        subnet.create_subnet(master_name, self.generate_cidr(), network.get_id(),
                             self.env[label]['dns_nameservers'])
        router.attach_subnet(subnet.get_id())

        # Instance
        logging.info('Creating master instance')
        master_userdata = list(self.env[label]['shared_userdata']) + list(self.env[label]['master']['userdata'])
        # Hard code command to run the master software
        master_userdata.append('python /opt/cloudpunch/cp_master/cp_master.py')
        instance = oscompute.Instance(self.sessions[label], self.creds[label].get_region(),
                                      self.env[label]['api_versions']['nova'])
        instance.create_instance(master_name,
                                 self.env[label]['image_name'],
                                 self.env[label]['master']['flavor'],
                                 network.get_id(),
                                 self.env[label]['master']['availability_zone'],
                                 self.keypairs[label][0].get_name(),
                                 self.secgroups[label][0].get_id(),
                                 self.config['retry_count'],
                                 master_userdata)
        self.instances[label].append(instance)

        # Attach floater
        floater = osnetwork.FloatingIP(self.sessions[label], self.creds[label].get_region(),
                                       self.env[label]['api_versions']['neutron'])
        floater.create_floatingip(self.ext_network[label].get_id())
        self.floaters[label].append(floater)
        instance.add_float(floater.get_ip())

        # Save information to connect to master
        self.master_ip = instance.get_ips()[0]
        if self.config['network_mode'] == 'full':
            self.master_ip = instance.get_ips()[1]
        self.master_url = 'http://%s' % instance.get_ips()[1]

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
                    router.create_router('%s-%s-r%s' % (self.cp_name, role[0], router_num),
                                         self.ext_network[label].get_id())
                    self.routers[label].append(router)

                    # Create number of networks per router based on config
                    for network_num in range(self.config['networks_per_router']):
                        network_num += 1
                        logging.info('Creating %s network %s of %s on router %s',
                                     role, network_num, self.config['networks_per_router'], router_num)
                        network = osnetwork.Network(self.sessions[label], self.creds[label].get_region(),
                                                    self.env[label]['api_versions']['neutron'])
                        network.create_network('%s-%s-r%s-n%s' % (self.cp_name, role[0], router_num, network_num))
                        self.networks[role].append(network)

                        # Create subnet for this network and attach to router
                        subnet = osnetwork.Subnet(self.sessions[label], self.creds[label].get_region(),
                                                  self.env[label]['api_versions']['neutron'])
                        subnet.create_subnet('%s-%s-r%s-n%s' % (self.cp_name, role[0], router_num, network_num),
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
                    network.create_network('%s-%s-master-n%s' % (self.cp_name, role[0], network_num))
                    self.networks[role].append(network)

                    # Create subnet for this network and attach to router
                    subnet = osnetwork.Subnet(self.sessions[label], self.creds[label].get_region(),
                                              self.env[label]['api_versions']['neutron'])
                    subnet.create_subnet('%s-%s-master-n%s' % (self.cp_name, role[0], network_num),
                                         self.generate_cidr(role=role, network_num=network_num),
                                         network.get_id(), self.env[label]['dns_nameservers'])
                    self.routers[label][0].attach_subnet(subnet.get_id())

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

        logging.info('Staging complete')

    def create_instance_map(self, roles, label):
        instance_map = []
        for role in roles:
            # network_mode full and single-router do not use the master network
            # network_mode single-network uses the the master
            networks = self.networks['master'] if self.config['network_mode'] == 'single-network' else self.networks[role]

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
                        'keypair': self.keypairs[label][0],
                        'secgroup': self.secgroups[label][0]
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

        slave_userdata = list(self.env[label]['shared_userdata']) + list(self.env[label][instance_map['role']]['userdata'])
        # Hard code command to run the slave software
        slave_userdata.append('python /opt/cloudpunch/cp_slave/cp_slave.py %s' % self.master_ip)

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
        instance.create_instance(instance_map['name'],
                                 self.env[label]['image_name'],
                                 instance_map['flavor'],
                                 instance_map['network'].get_id(),
                                 avail_zone,
                                 instance_map['keypair'].get_name(),
                                 instance_map['secgroup'].get_id(),
                                 self.config['retry_count'],
                                 user_data=slave_userdata,
                                 boot_from_vol=vol_boot)
        self.instances[label].append(instance)

        # Create a volume if configuration has it enabled
        if ('volume' in self.env[label][instance_map['role']] and
                self.env[label][instance_map['role']]['volume']['enable']):
            # Check if volume exists. Recovery mode does not delete volume
            skip_creation = False
            for v in self.volumes[label]:
                if v.get_name() == instance_map['name']:
                    skip_creation = True
                    volume = v
                    break
            # Create cinder volume
            if not skip_creation:
                volume = osvolume.Volume(self.sessions[label], self.creds[label].get_region(),
                                         self.env[label]['api_versions']['cinder'])
                volume.create_volume(self.env[label][instance_map['role']]['volume']['size'],
                                     instance_map['name'],
                                     volume_type=self.env[label][instance_map['role']]['volume']['type'])
                self.volumes[label].append(volume)

            # Attach volume to instance
            instance.attach_volume(volume.get_id())

        # Only network_mode full puts floating IP addresses on slaves
        if self.config['network_mode'] == 'full':
            # Allocate a floating IP address
            floater = osnetwork.FloatingIP(self.sessions[label], self.creds[label].get_region(),
                                           self.env[label]['api_versions']['neutron'])
            floater.create_floatingip(self.ext_network[label].get_id())
            self.floaters[label].append(floater)

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
            # Same as above but not taking into account the number of routers or network
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

    def show_environment(self):
        # Creates a table to show instance information
        table = [['Instance Name', 'Internal IP', 'Floating IP']]
        for label in ['env1', 'env2']:
            for instance in self.instances[label]:
                # index 0 is always the instance's private IP
                # index 1 is always the instance's floating IP
                ips = instance.get_ips()
                floating_ip = ips[1] if len(ips) > 1 else '-'
                row = [instance.get_name(), ips[0], floating_ip]
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
        total_servers = len(self.instances['env1']) + len(self.instances['env2']) - 1
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
                print 'Not a valid recovery type'
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
                        self.instances[label].remove(instance)
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
            # Call self to restart registration process
            self.connect_to_master()
            # Set to all registered as to not say all instances are not registered
            registered_servers = total_servers
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
        missing_instances = list(self.instances['env1']) + list(self.instances['env2'])
        for instance_obj in list(self.instances['env1']) + list(self.instances['env2']):
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
        # Send test information to Datadog as an Event
        if self.config['datadog']['enable']:
            self.test_started = True
            self.sendDatadogEvent('Starting Test: %s' % (self.cp_id),
                                  'Tests:%s\nRNI:%s:%s:%s\nMode:%s' % (','.join(self.config['test']),
                                                                       self.config['number_routers'],
                                                                       self.config['networks_per_router'],
                                                                       self.config['instances_per_network'],
                                                                       self.config['network_mode']))
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
        total_servers = len(self.instances['env1']) + len(self.instances['env2']) - 1
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
            ofile = open(output_file, 'w')
            ofile.write(results)
            ofile.close()
        else:
            logging.info('Results: \n%s' % results)

        # Ask user to start another test if reuse_mode is enabled
        if self.reuse_mode:
            # User can enter the full word or just the first letter
            regex = '^(s(ame)?|d(ifferent)?|a(bort)?)$'
            newtest_type = raw_input('Enter new test type (same, different, abort) ')
            match = re.search(regex, newtest_type)
            while not match:
                print 'Not a valid new test type'
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
                            print e.message
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
        # Signal to datadog that the test has completed
        if self.config['datadog']['enable'] and self.test_started:
            self.sendDatadogEvent('Test Complete: %s' % self.cp_id, '')

        logging.info('Checking for resources to cleanup')
        labels = ['env1']
        if self.creds['env2']:
            labels.append('env2')

        # Delete resources if cleanup_resources is enabled
        if self.config['cleanup_resources']:
            for label in labels:
                self.cleanup_project(label)

        # Save cleanup information if resources still exist
        for label in labels:
            self.check_resources(label)

    def cleanup_project(self, label):
        location = self.creds[label].get_creds()['auth_url']
        region = self.creds[label].get_creds()['region_name']
        if self.instances[label]:
            logging.info('Deleting instances on %s under region %s', location, region)
            for instance in self.instances[label][:]:
                # Detach volume and floating IP from instance before deleting
                # Seems to provide a more reliable delete
                instance.detach_volume()
                instance.remove_float()
                if instance.delete_instance():
                    self.instances[label].remove(instance)

        if self.volumes[label]:
            logging.info('Deleting volumes on %s under region %s', location, region)
            for volume in self.volumes[label][:]:
                if volume.delete_volume():
                    self.volumes[label].remove(volume)

        if self.floaters[label]:
            logging.info('Deleting floating ips on %s under region %s', location, region)
            for floater in self.floaters[label][:]:
                if floater.delete_floatingip():
                    self.floaters[label].remove(floater)

        if self.routers[label]:
            logging.info('Deleting routers on %s under region %s', location, region)
            for router in self.routers[label][:]:
                if router.delete_router():
                    self.routers[label].remove(router)

        # env1 has all 3 roles if split mode is disabled
        roles = ['master', 'server', 'client']
        if self.creds['env2']:
            # env1 has master and server roles if split mode is enabled
            if label == 'env1':
                roles = ['master', 'server']
            # env2 has only the client role
            else:
                roles = ['client']
        for role in roles:
            if self.networks[role]:
                logging.info('Deleting %s networks on %s under region %s', role, location, region)
                for network in self.networks[role][:]:
                    if network.delete_network():
                        self.networks[role].remove(network)

        if self.keypairs[label]:
            logging.info('Deleting keypairs on %s under region %s', location, region)
            for keypair in self.keypairs[label][:]:
                if keypair.delete_keypair():
                    self.keypairs[label].remove(keypair)

        if self.secgroups[label]:
            logging.info('Deleting security groups on %s under region %s', location, region)
            for secgroup in self.secgroups[label][:]:
                if secgroup.delete_secgroup():
                    self.secgroups[label].remove(secgroup)

        if self.users[label]:
            logging.info('Deleting users on %s under region %s', location, region)
            for user in self.users[label][:]:
                if user.delete_user():
                    self.users[label].remove(user)

        if self.projects[label]:
            logging.info('Deleting projects on %s under region %s', location, region)
            for project in self.projects[label][:]:
                if project.delete_project():
                    self.projects[label].remove(project)

    def check_resources(self, label):
        cleanup = {}

        if self.volumes[label]:
            cleanup['volumes'] = []
            for volume in self.volumes[label]:
                cleanup['volumes'].append(volume.get_id())

        if self.instances[label]:
            cleanup['instances'] = []
            for instance in self.instances[label]:
                cleanup['instances'].append(instance.get_id())

        if self.floaters[label]:
            cleanup['floaters'] = []
            for floater in self.floaters[label]:
                cleanup['floaters'].append(floater.get_id())

        if self.routers[label]:
            cleanup['routers'] = []
            for router in self.routers[label]:
                cleanup['routers'].append(router.get_id())

        roles = ['master', 'server', 'client']
        if self.creds['env2']:
            if label == 'env1':
                roles = ['master', 'server']
            else:
                roles = ['client']
        for role in roles:
            if self.networks[role]:
                name = '%s-network' % role
                cleanup[name] = []
                for network in self.networks[role]:
                    cleanup[name].append(network.get_id())

        if self.keypairs[label]:
            cleanup['keypairs'] = []
            for keypair in self.keypairs[label]:
                cleanup['keypairs'].append(keypair.get_name())

        if self.secgroups[label]:
            cleanup['secgroups'] = []
            for secgroup in self.secgroups[label]:
                cleanup['secgroups'].append(secgroup.get_id())

        if self.users[label]:
            cleanup['users'] = []
            for user in self.users[label]:
                cleanup['users'].append(user.get_id())

        if self.projects[label]:
            cleanup['projects'] = []
            for project in self.projects[label]:
                cleanup['projects'].append(project.get_id())

        if cleanup:
            # Add OpenStack API versions to cleanup file
            cleanup['api_versions'] = self.env[label]['api_versions']
            # The name is based on ID and env
            fname = '%s-%s-cleanup.json' % (self.cp_name, label)
            cleanup_file = open(fname, 'w')
            cleanup_file.write(json.dumps(cleanup))
            cleanup_file.close()
            logging.info('CloudPunch resources still exist on OpenStack. Run cloudpunch-cleanup to remove these resources')
            logging.info('Saved deletion information to %s', fname)

    def sendDatadogEvent(self, title, message):
        # Used to send an event to Datadog
        options = {
            'api_key': self.config['datadog']['api_key']
        }
        datadog.initialize(**options)
        datadog.api.Event.create(title=title, text=message, tags=self.config['datadog']['tags'])


class CPError(Exception):
    pass


class CPStop(Exception):
    pass
