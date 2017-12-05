import json
import copy
import logging
import sys
import traceback

from flask import Flask, abort, request

# Test configuration
CONFIG = {}
# Results from workers
RESULTS = []
# List of all OpenStack worker instances
INSTANCES = []
# List of all workers with the role server
SERVERS = []
# List of all workers with the role client
CLIENTS = []
# Currently running workers
RUNNING = []
# Signals the start of the test
MATCHED = False
app = Flask(__name__)
app.config.from_object(__name__)


@app.errorhandler(400)
def bad_request(error):
    # Handles 400 errors
    return json.dumps({'error': error.description}), 400, {'Content-Type': 'text/json; charset=utf-8'}


@app.errorhandler(404)
def not_found(error):
    # Handles 404 errors
    return json.dumps({'error': error.description}), 404, {'Content-Type': 'text/json; charset=utf-8'}


@app.errorhandler(500)
def server_error(error):
    type_, value_, traceback_ = sys.exc_info()
    logging.error('Exception raised...')
    for line in traceback.format_tb(traceback_):
        logging.error(line.strip())
    logging.error('%s: %s' % (type_.__name__, value_))
    message = json.dumps({'error': '%s: %s' % (type(error).__name__, error.message)})
    return message, 500, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/system/health', methods=['GET'])
def get_syshealth():
    # Used to test if the API is up
    return json.dumps({'status': 'OK'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/register', methods=['GET'])
def get_registered():
    # Returns a list of instances that have registered
    instances = app.config['INSTANCES']
    response = {
        'count': len(instances),
        'instances': instances
    }
    return json.dumps(response), 200, {'Content-Type': 'text/json; charset=utf-8'}


# {
#     'hostname': '',
#     'internal_ip: '',
#     'external_ip: '',
#     'role': ''
# }

@app.route('/api/register', methods=['POST'])
def register_server():
    # Loads in information above to register an instance
    if not request.json:
        abort(400, 'Missing host data')
    internal_ip = request.json.get('internal_ip')
    external_ip = request.json.get('external_ip')
    hostname = request.json.get('hostname')
    role = request.json.get('role')
    if not internal_ip or not external_ip or not hostname or not role:
        abort(400, 'Missing host data')
    instance = {
        'hostname': hostname,
        'internal_ip': internal_ip,
        'external_ip': external_ip,
        'role': role
    }
    app.config['INSTANCES'].append(instance)
    return json.dumps({'status': 'registered'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/config', methods=['GET'])
def get_config():
    # Returns the saved configuration received from local machine
    config = app.config['CONFIG']
    response = config if config else json.dumps({})
    return response, 200, {'Content-Type': 'text/json; charset=utf-8'}


# config file dictionary

@app.route('/api/config', methods=['POST'])
def give_config():
    # Loads in the configuration dictionary from the local machine
    if not request.json:
        abort(400, 'Missing configuration')
    app.config['CONFIG'] = request.json
    return json.dumps({'status': 'saved'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


def get_instance_num(config, instance_name):
    # Split the name to find relevant information
    instance_name_split = instance_name.split('-')
    # network_mode full looks at router, network, and instance number
    if config['network_mode'] == 'full':
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
        first_num = (rtr_num - 1) * config['networks_per_router'] * config['instances_per_network']
        # The second number is taking into account the number of instances before this network on this router
        # In this case there were 2 instances before this one on this router
        second_num = (net_num - 1) * config['instances_per_network']
        # Add these numbers together with the instance number
        return first_num + second_num + inst_num
        # Getting a result of 3
    elif config['network_mode'] == 'single-router':
        # Same as above but not taking into account the number of routers
        net_num = int(instance_name_split[4][1:])
        inst_num = int(instance_name_split[5][1:])
        second_num = (net_num - 1) * config['instances_per_network']
        return second_num + inst_num
    elif config['network_mode'] == 'single-network':
        # Same as above but not taking into account the number of routers or network
        return int(instance_name_split[3][1:])


@app.route('/api/test/match', methods=['GET'])
def match_servers():
    # Matches server and client instances based on their instance number (they equal each other)
    config = app.config['CONFIG']
    if not app.config['SERVERS']:
        instances = app.config['INSTANCES']
        # Premake the lists
        # This allows setting values everywhere
        if config['server_client_mode']:
            servers = [None] * (len(instances) / 2)
            clients = [None] * (len(instances) / 2)
        else:
            servers = [None] * len(instances)
            clients = []
        for instance in instances:
            inst_num = get_instance_num(config, instance['hostname'])
            if instance['role'] == 'server':
                servers[inst_num - 1] = instance
            elif instance['role'] == 'client':
                clients[inst_num - 1] = instance
        app.config['SERVERS'] = servers
        app.config['CLIENTS'] = clients
    app.config['MATCHED'] = True
    return json.dumps({'status': 'matched'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


# {
#     'hostname': ''
# }

@app.route('/api/test/status', methods=['POST'])
def test_status():
    # Controls if an instance starts the test
    # Hostname is provided in the POST body
    if not request.json:
        abort(400, 'Missing hostname')
    hostname = request.json.get('hostname')
    if not hostname:
        abort(400, 'Missing hostname')
    if app.config['MATCHED']:
        # A list of servers that have asked to start the test
        # This list is reset when restarting the test
        # Tell the server to hold because it has asked once before reset
        if hostname in app.config['RUNNING']:
            response = {'status': 'hold'}
        # Tell the server to start the test
        else:
            response = {'status': 'go'}
            # Add to currently running servers
            app.config['RUNNING'].append(hostname)
    else:
        response = {'status': 'hold'}
    return json.dumps(response), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/test/status', methods=['DELETE'])
def delete_status():
    # Reset test information
    app.config['RUNNING'] = []
    app.config['RESULTS'] = []
    return json.dumps({'status': 'deleted'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


def get_network_num(config, instance_name):
    if config['network_mode'] == 'single-network':
        return 1
    instance_name_split = instance_name.split('-')
    if config['network_mode'] == 'full':
        # cloudpunch-9079364-c-r1-n1-c1
        router_num = int(instance_name_split[3][1:])
        network_num = int(instance_name_split[4][1:])
        first_num = (router_num - 1) * config['networks_per_router']
        return first_num + network_num
    elif config['network_mode'] == 'single-router':
        # cloudpunch-9079364-c-r1-n1-c1
        return int(instance_name_split[4][1:])


def get_index(data, hostname):
    try:
        return next(index for (index, d) in enumerate(data) if d['hostname'] == hostname)
    except StopIteration:
        return -1


def get_role(hostname):
    name_split = hostname.split('-')
    if name_split[5][0] == 's':
        return 'server'
    if name_split[5][0] == 'c':
        return 'client'
    return None


# {
#     'hostname': ''
# }

@app.route('/api/test/run', methods=['POST'])
def test_run():
    # Returns test information to instances
    # Hostname is given in the POST body
    if not request.json:
        abort(400, 'Missing required data')
    hostname = request.json.get('hostname')
    if not hostname:
        abort(400, 'Missing hostname')
    role = get_role(hostname)
    config = copy.deepcopy(app.config['CONFIG'])
    if not config:
        abort(404, 'No configuration exists')
    # Match up loadbalancers IP addresses based on the network an instance is on
    if 'loadbalancers' in config:
        if role == 'server' and 'client' in config['loadbalancers']:
            config['match_ip'] = config['loadbalancers']['client'][get_network_num(config, hostname) - 1]
        elif role == 'client' and 'server' in config['loadbalancers']:
            config['match_ip'] = config['loadbalancers']['server'][get_network_num(config, hostname) - 1]
    # Match up instance IP addresses using the lists made in match_servers()
    # Matched instances share the same index number
    # network_mode full gives floating IP addresses, single-router and single-network give internal IP addresses
    if 'match_ip' not in config and config['server_client_mode']:
        servers = app.config['SERVERS']
        clients = app.config['CLIENTS']
        wanted_ip = 'internal_ip'
        if config['network_mode'] == 'full':
            wanted_ip = 'external_ip'
        if role == 'server':
            server_index = get_index(servers, hostname)
            if server_index >= 0:
                config['match_ip'] = clients[server_index][wanted_ip]
            else:
                abort(404, 'No match found')
        elif role == 'client':
            client_index = get_index(clients, hostname)
            if client_index >= 0:
                config['match_ip'] = servers[client_index][wanted_ip]
            else:
                abort(404, 'No match found')
    return json.dumps(config), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/test/results', methods=['GET'])
def test_results():
    # Return the test results
    return json.dumps(app.config['RESULTS']), 200, {'Content-Type': 'text/json; charset=utf-8'}


# {
#     'hostname': '',
#     'results': ''
# }

@app.route('/api/test/results', methods=['POST'])
def give_results():
    # Loads in test results from instances
    # Hostname and results are given in the POST body
    if not request.json:
        abort(400, 'Missing hostname and result data')
    hostname = request.json.get('hostname')
    results = request.json.get('results')
    if not hostname or not results:
        abort(400, 'Missing hostname and result data')
    app.config['RESULTS'].append({'hostname': hostname, 'results': results})
    return json.dumps({'status': 'saved'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


def run(host, port, debug):
    if not debug:
        app.logger.disabled = True
    app.run(host=host, port=int(port), debug=debug)
