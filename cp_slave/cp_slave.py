import sys
import requests
import logging
import time
import json
import importlib
import os

import sysinfo

LOGLEVEL = 'INFO'
LOGFILE = '/tmp/cp-slave.log'
LOGFORMAT = '%(asctime)-15s %(levelname)s %(message)s'
DATEFORMAT = '%Y-%m-%d %H:%M:%S'


class CPSlaveError(Exception):
    pass


def slave():
    numeric_level = getattr(logging, LOGLEVEL, None)
    logging.basicConfig(format=LOGFORMAT,
                        datefmt=DATEFORMAT,
                        level=numeric_level,
                        filename=LOGFILE)

    # Master server's IP is given as first and only argument
    if len(sys.argv) < 2:
        raise CPSlaveError('Missing master ip, exiting')
    baseurl = 'http://%s' % sys.argv[1]

    # Wait for master to be ready
    status = 0
    while status != 200:
        logging.info('Attempting to connect to master server')
        try:
            request = requests.get('%s/api/system/health' % baseurl, timeout=3)
            status = request.status_code
        except requests.exceptions.RequestException:
            status = 0
        if status != 200:
            time.sleep(1)
    logging.info('Connected successfully to master server')

    # Register to master server
    hostname = sysinfo.hostname()
    register_body = {
        'hostname': hostname,
        'internal_ip': sysinfo.ip(),
        'external_ip': sysinfo.floating(),
        'role': sysinfo.role()
    }
    status = 0
    while status != 200:
        logging.info('Attempting to register to master server')
        try:
            request = requests.post('%s/api/register' % baseurl, json=register_body, timeout=3)
            status = request.status_code
        except requests.exceptions.RequestException:
            status = 0
        if status != 200:
            time.sleep(1)
    logging.info('Registered to master server')

    # Infinite loop when more than one test is to be run
    while True:
        # Wait for test status to be go
        status_body = {
            'hostname': hostname
        }
        status = 'hold'
        while status != 'go':
            logging.info('Waiting for test status to be go')
            try:
                request = requests.post('%s/api/test/status' % baseurl, json=status_body, timeout=3)
                data = json.loads(request.text)
                status = data['status']
            except (requests.exceptions.RequestException, ValueError, KeyError):
                pass
            if status != 'go':
                time.sleep(1)
        logging.info('Test status is go, starting test')

        # Get test information from master
        test_body = {
            'hostname': hostname
        }
        status = 0
        while status != 200:
            logging.info('Attempting to get test information from master')
            try:
                request = requests.post('%s/api/test/run' % baseurl, json=test_body, timeout=3)
                status = request.status_code
            except requests.exceptions.RequestException:
                status = 0
            if status != 200:
                time.sleep(1)
        config = json.loads(request.text)
        logging.info('Got test information from master')

        # Log information
        config['role'] = sysinfo.role()
        logging.info('I am running the test(s) %s', ', '.join(config['test']))
        logging.info('My role is %s', config['role'])
        if 'match_ip' in config:
            logging.info('My corresponding instance is %s', config['match_ip'])
        else:
            logging.info('I do not have a corresponding instance')

        # Edit datadog configuration if enabled
        if config['datadog']['enable']:
            os.popen('echo \"hostname: %s\" >> /etc/dd-agent/datadog.conf' % hostname)
            tag_string = ','.join(config['datadog']['tags'])
            tags = '%s, role:%s' % (tag_string, sysinfo.role())
            os.popen('echo \"tags: %s\" >> /etc/dd-agent/datadog.conf' % tags)
            os.popen('service datadog-agent restart')

            # Modify the nice value of the datadog pids
            if 'nice' in config['datadog']:
                try:
                    os.popen('for i in $(ps ax | grep datadog-agent |'
                             ' awk \'{print $1}\'); do renice -n %s -p $i; done' % config['datadog']['nice'])
                except Exception as e:
                    logging.error('Datadog nice error: %s', e.message)

        try:
            test_results = {}
            if config['test_mode'] == 'list':
                logging.info('I am running tests one at a time')
                threads = []
                # Add tests to thread list
                for test_name in config['test']:
                    module = importlib.import_module(test_name)
                    t = module.CloudPunchTest(config)
                    threads.append(t)
                # Run each test thread
                for t in threads:
                    if 'test_start_delay' in config:
                        time.sleep(config['test_start_delay'])
                    logging.info('Starting test %s', t.__module__)
                    t.start()
                    t.join()
                    if t.final_results:
                        test_results[t.__module__] = t.final_results

            elif config['test_mode'] == 'concurrent':
                logging.info('I am starting all the tests at once')
                threads = []
                # Add tests to thread list
                for test_name in config['test']:
                    module = importlib.import_module(test_name)
                    t = module.CloudPunchTest(config)
                    threads.append(t)
                if 'test_start_delay' in config:
                    time.sleep(config['test_start_delay'])
                # Run each test thread
                for t in threads:
                    logging.info('Starting test %s', t.__module__)
                    t.start()
                # Wait for all tests to complete
                for t in threads:
                    t.join()
                    if t.final_results:
                        test_results[t.__module__] = t.final_results
            else:
                logging.error('Unknown test mode %s', config['test_mode'])
        except Exception as e:
            logging.error('%s: %s', type(e).__name__, e.message)
        logging.info('All tests have finished')

        # Send results to master if required
        send_results = False
        if config['server_client_mode']:
            if config['role'] == 'server' and config['servers_give_results']:
                send_results = True
            elif config['role'] == 'client':
                send_results = True
        else:
            send_results = True
        if send_results:
            if not test_results:
                logging.error('Expected to send results but no results to send')
                test_results = 'Expected to send results but no results to send'
            test_result_body = {
                'hostname': hostname,
                'results': test_results
            }
            status = 0
            while status != 200:
                logging.info('Attempting to send test results to master')
                try:
                    request = requests.post('%s/api/test/results' % baseurl, json=test_result_body, timeout=3)
                    status = request.status_code
                except requests.exceptions.RequestException:
                    status = 0
                if status != 200:
                    time.sleep(1)
            logging.info('Sent test results to master')
        else:
            logging.info('Not expected to send results')
        logging.info('Test process complete. Starting over')


def main():
    try:
        slave()
    except CPSlaveError as e:
        logging.error(e.message)
    finally:
        logging.info('Terminating CloudPunch slave')


if __name__ == '__main__':
    main()
