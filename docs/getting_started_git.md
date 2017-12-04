# Git Installation

This installation method is used to run the Python source code directory or for code development

#### 1. Install Dependencies

###### Ubuntu/Debian

```
sudo apt-get install python-dev python-virtualenv git
```

###### RHEL/CentOS

```
sudo yum install python-devel python-virtualenv git
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

#### 3. Clone GitHub Repo

```
git clone https://github.com/target/cloudpunch.git
```

#### 4. Install CloudPunch

```
cd cloudpunch/
python setup.py install
```

#### 5. Verify Installation

```
$ cloudpunch -h
usage: cloudpunch [-h] [-v] [-l LOG_LEVEL] [-L LOG_FILE]
                  {run,cleanup,post,worker} ...

Framework for OpenStack performance testing

positional arguments:
  {run,cleanup,post,worker}
                        workloads
    run                 run a test
    cleanup             cleanup resources
    post                process results
    worker              start a worker server

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -l LOG_LEVEL, --loglevel LOG_LEVEL
                        log level (default: INFO)
  -L LOG_FILE, --logfile LOG_FILE
                        file to log to (default: stdout)
```
