import logging

from netifaces import interfaces, ifaddresses, AF_INET


# Hint can be a network interface or an IP address
def find_ip_address(hint):
    intMap = {}
    ips = []
    for name in interfaces():
        addresses = [i['addr'] for i in ifaddresses(name).setdefault(AF_INET, [])]
        if addresses:
            intMap[name] = addresses
            ips += addresses
    # If no hint is provided, use the first found interface and IP address
    if not hint:
        interface = intMap.keys()[0]
        ip = intMap[interface][0]
        logging.info('No connect parameter supplied, using IP address %s from interface %s for '
                     'connectivity from workers', ip, interface)
        return ip
    # Check if provided hint is a valid interface
    if hint in interfaces():
        if hint not in intMap:
            raise NetworkUtilError('Interface %s has no IP address' % hint)
        logging.info('Using IP address %s from interface %s for connectivity from workers', intMap[hint][0], hint)
        return intMap[hint][0]
    # Check if provided hint is an IP address on any interface
    if hint in ips:
        return hint
    # Return back hint and a warning
    logging.warning('Provided connect parameter %s is not an interface or IP address on this machine.'
                    ' This may cause issues with connectivity from workers', hint)
    return hint


class NetworkUtilError(Exception):

    def __init__(self, message):
        super(NetworkUtilError, self).__init__(message)
        self.message = message
