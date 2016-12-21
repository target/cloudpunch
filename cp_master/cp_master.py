import json
import redis

from flask import Flask, abort, request

app = Flask(__name__)
__host__ = '0.0.0.0'
__port__ = 80


@app.errorhandler(400)
def bad_request(error):
    # Handles 400 errors
    return json.dumps({'error': error.description}), 400, {'Content-Type': 'text/json; charset=utf-8'}


@app.errorhandler(404)
def not_found(error):
    # Handles 404 errors
    return json.dumps({'error': error.description}), 404, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/system/health', methods=['GET'])
def get_syshealth():
    # Used to test if the API is up
    return json.dumps({'status': 'OK'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/register', methods=['GET'])
def get_registered():
    # Returns a list of instances that have registered
    r_server = redis.Redis('localhost')
    data = r_server.get('instances')
    instances = json.loads(data) if data else []
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
    r_server = redis.Redis('localhost')
    instances = r_server.get('instances')
    data = json.loads(instances) if instances else []
    data.append(instance)
    r_server.set('instances', json.dumps(data))
    return json.dumps({'status': 'registered'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/config', methods=['GET'])
def get_config():
    # Returns the saved configuration received from local machine
    r_server = redis.Redis('localhost')
    config = r_server.get('config')
    response = config if config else json.dumps({})
    return response, 200, {'Content-Type': 'text/json; charset=utf-8'}


# config file dictionary

@app.route('/api/config', methods=['POST'])
def give_config():
    # Loads in the configuration dictionary from the local machine
    if not request.json:
        abort(400, 'Missing configuration')
    r_server = redis.Redis('localhost')
    r_server.set('config', json.dumps(request.json))
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
    r_server = redis.Redis('localhost')
    if not r_server.get('servers'):
        instances = json.loads(r_server.get('instances'))
        config = json.loads(r_server.get('config'))
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
        r_server.set('servers', json.dumps(servers))
        r_server.set('clients', json.dumps(clients))
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
    r_server = redis.Redis('localhost')
    servers = r_server.get('servers')
    if servers:
        # A list of servers that have asked to start the test
        # This list is reset when restarting the test
        running = r_server.get('running')
        running_servers = json.loads(running) if running else []
        # Tell the server to hold because it has asked once before reset
        if hostname in running_servers:
            response = {'status': 'hold'}
        # Tell the server to start the test
        else:
            response = {'status': 'go'}
            # Add to currently running servers
            running_servers.append(hostname)
            r_server.set('running', json.dumps(running_servers))
    else:
        response = {'status': 'hold'}
    return json.dumps(response), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/test/status', methods=['DELETE'])
def delete_status():
    # Reset test information
    r_server = redis.Redis('localhost')
    r_server.delete('running')
    r_server.delete('results')
    return json.dumps({'status': 'deleted'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


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
    r_server = redis.Redis('localhost')
    # Load configuration
    data = r_server.get('config')
    if data:
        config = json.loads(data)
    else:
        abort(404, 'No configuration exists')
    # Match up instance IP addresses using the lists made in match_servers()
    # Matched instances share the same index number
    # network_mode full gives floating IP addresses, single-router and single-network give internal IP addresses
    if config['server_client_mode']:
        match_ip = ''
        servers = json.loads(r_server.get('servers'))
        clients = json.loads(r_server.get('clients'))
        for index in range(len(servers)):
            if servers[index]['hostname'] == hostname:
                match_ip = clients[index]['internal_ip']
                if config['network_mode'] == 'full':
                    match_ip = clients[index]['external_ip']
            elif clients[index]['hostname'] == hostname:
                match_ip = servers[index]['internal_ip']
                if config['network_mode'] == 'full':
                    match_ip = servers[index]['external_ip']
        if len(match_ip) < 1:
            abort(404, 'No match found')
        config['match_ip'] = match_ip
    return json.dumps(config), 200, {'Content-Type': 'text/json; charset=utf-8'}


@app.route('/api/test/results', methods=['GET'])
def test_results():
    # Return the test results
    r_server = redis.Redis('localhost')
    all_results = r_server.get('results')
    response = all_results if all_results else json.dumps([])
    return response, 200, {'Content-Type': 'text/json; charset=utf-8'}


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
    r_server = redis.Redis('localhost')
    all_results = r_server.get('results')
    data = json.loads(all_results) if all_results else []
    data.append({'hostname': hostname, 'results': results})
    r_server.set('results', json.dumps(data))
    return json.dumps({'status': 'saved'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


if __name__ == '__main__':
    app.run(host=__host__, port=__port__, debug=True)
