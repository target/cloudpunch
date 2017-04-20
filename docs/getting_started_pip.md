# PIP Installation

This installation method is recommended as it will handle all installation requirements and install a binary

#### 1. Install Dependencies

###### Ubuntu/Debian

```
sudo apt-get install python-dev python-virtualenv
```

###### RHEL/CentOS

```
sudo yum install python-devel python-virtualenv
```

###### Mac OS X

```
xcode-select --install
sudo easy_install pip
sudo pip install virtualenv
```

#### 2. Setup Virtual Environment (Optional)

```
virtualenv ./vcloudpunch
source ./vcloudpunch/bin/activate
```

#### 3. Install CloudPunch

```
pip install cloudpunch
```

#### 4. Verify Installation

```
$ cloudpunch -h
usage: cloudpunch [-h] [-v] [-l LOG_LEVEL] [-L LOG_FILE]
                  {run,cleanup,post,master,slave} ...

Framework for OpenStack performance testing

positional arguments:
  {run,cleanup,post,master,slave}
                        workloads
    run                 run a test
    cleanup             cleanup resources
    post                process results
    master              start the master server
    slave               start a slave server

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -l LOG_LEVEL, --loglevel LOG_LEVEL
                        log level (default: INFO)
  -L LOG_FILE, --logfile LOG_FILE
                        file to log to (default: stdout)
```
