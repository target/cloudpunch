import os


def hostname():
    hostname = os.popen('hostname').read()
    return hostname.rstrip().lower()


def role():
    name = hostname()
    name_split = name.split('-')
    if name_split[2] == 'master':
        if name_split[3][0] == 's':
            return 'server'
        if name_split[3][0] == 'c':
            return 'client'
    if name_split[2] == 's':
        return 'server'
    if name_split[2] == 'c':
        return 'client'
    return None


def ip():
    ip = os.popen('/sbin/ip -4 -o addr show dev eth0| awk \'{split($4,a,"/");print a[1]}\'').read()
    return ip.rstrip()


def floating():
    floating = os.popen('curl -s http://169.254.169.254/2009-04-04/meta-data/public-ipv4').read()
    return floating.rstrip() if floating else '0.0.0.0'
