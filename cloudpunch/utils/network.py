import logging
import socket
import requests
import time

from netifaces import interfaces, ifaddresses, AF_INET

from cloudpunch.utils import exceptions


# Hint can be a network interface or an IP address
def find_ip_address(hint):
    intMap = {}
    ipMap = {}
    for name in interfaces():
        addresses = [i['addr'] for i in ifaddresses(name).setdefault(AF_INET, [])]
        if addresses:
            intMap[name] = addresses[0]
            ipMap[addresses[0]] = name
    # If no hint is provided, guess the interface based on where external traffic gets routed to
    if not hint:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        logging.info('No connect parameter supplied, using IP address %s from interface %s for '
                     'connectivity from workers', ip, ipMap[ip])
        return ip
    # Check if provided hint is a valid interface
    if hint in interfaces():
        if hint not in intMap:
            raise exceptions.CPError('Interface %s has no IP address' % hint)
        logging.info('Using IP address %s from interface %s for connectivity from workers', intMap[hint], hint)
        return intMap[hint]
    # Check if provided hint is an IP address on any interface
    if hint in ipMap:
        return hint
    # Return back hint and a warning
    logging.warning('Provided connect parameter %s is not an interface or IP address on this machine.'
                    ' This may cause issues with connectivity from workers', hint)
    return hint


def request_by_status(url, retry_count=10, sleep_time=2, attempt_msg='', success_msg='', fail_msg=''):
    if retry_count == -1:
        retry_count = 999999
    status = 0
    for num in range(retry_count):
        if attempt_msg:
            logging.info('%s. Retry %s of %s', attempt_msg, num + 1, retry_count)
        try:
            request = requests.get(url, timeout=3)
            status = request.status_code
            response = request.text
        except requests.exceptions.RequestException:
            status = 0
        if status == 200:
            if success_msg:
                logging.info(success_msg)
            return (status, response)
        time.sleep(sleep_time)
    if status != 200:
        raise exceptions.CPError(fail_msg)


def request_send(url, json, retry_count=10, sleep_time=1, attempt_msg='', success_msg='', fail_msg=''):
    if retry_count == -1:
        retry_count = 999999
    status = 0
    for num in range(retry_count):
        if attempt_msg:
            logging.info('%s. Retry %s of %s', attempt_msg, num + 1, retry_count)
        try:
            request = requests.post(url, json=json, timeout=3)
            status = request.status_code
            response = request.text
        except requests.exceptions.RequestException:
            status = 0
        if status == 200:
            if success_msg:
                logging.info(success_msg)
            return (status, response)
        time.sleep(sleep_time)
    if status != 200:
        raise exceptions.CPError(fail_msg)
