import os


def hostname():
    hostname = os.popen('hostname').read()
    return hostname.rstrip().lower().split('.')[0]


def testnum():
    return hostname().split('-')[1]


def role():
    name = hostname()
    name_split = name.split('-')
    if name_split[5][0] == 's':
        return 'server'
    if name_split[5][0] == 'c':
        return 'client'
    return None


def ip():
    ip = os.popen('/sbin/ip -4 -o addr show dev eth0| awk \'{split($4,a,"/");print a[1]}\'').read()
    return ip.rstrip()


def floating():
    floating = os.popen('curl -s http://169.254.169.254/2009-04-04/meta-data/public-ipv4').read()
    return floating.rstrip() if floating else '0.0.0.0'
