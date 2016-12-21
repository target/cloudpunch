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

usage: cloudpunch [-h] [-v] [-c CONFIG_FILE] [-e ENV_FILE] [-e2 ENV2_FILE]
                   [-r OPENRC_FILE] [-r2 OPENRC2_FILE] [-m HOSTMAP_FILE]
                   [-f FLAVOR_FILE] [-o OUTPUT_FILE] [-p PASSWORD]
                   [-p2 PASSWORD2] [--no-env] [--admin] [--split] [--manual]
                   [--reuse] [--yaml] [--insecure] [-l LOG_LEVEL]
                   [-L LOG_FILE]

Framework for OpenStack performance testing

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -c CONFIG_FILE, --config CONFIG_FILE
                        override default configuration with a config file
  -e ENV_FILE, --env ENV_FILE
                        override default environment with an environment file
  -e2 ENV2_FILE, --env2 ENV2_FILE
                        environment for second OpenStack instance
  -r OPENRC_FILE, --openrc OPENRC_FILE
                        OpenRC file containing authentication info (default:
                        env)
  -r2 OPENRC2_FILE, --openrc2 OPENRC2_FILE
                        OpenRC file for second OpenStack instance
  -m HOSTMAP_FILE, --hostmap HOSTMAP_FILE
                        file containg a hostmap to control instance location
  -f FLAVOR_FILE, --flavor FLAVOR_FILE
                        file containing a flavor breakdown
  -o OUTPUT_FILE, --output OUTPUT_FILE
                        file to save results to (default: stdout)
  -p PASSWORD, --password PASSWORD
                        password to login (only use when non-interactive)
  -p2 PASSWORD2, --password2 PASSWORD2
                        password to login into second OpenStack instance
  --no-env              do not use environment for authentication
  --admin               enable admin mode (create own tenant and user)
  --split               enable split mode (two OpenStack instances)
  --manual              enable manual test start (requires interactive)
  --reuse               enable reuse mode (run another test after completion,
                        requires interactive)
  --yaml                results are yaml instead of json
  --insecure            ignore SSL failures
  -l LOG_LEVEL, --loglevel LOG_LEVEL
                        log level (default: INFO)
  -L LOG_FILE, --logfile LOG_FILE
                        file to log to (default: stdout)
```
