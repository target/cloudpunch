# Getting Started

## OpenStack Prerequisites

- Access to OpenStack cloud (admin access optional)
- Neutron networking
- External network attached to OpenStack cloud
- n floating IPs only if networking mode is full
    - n is number of servers + clients (if server_client_mode is enabled)

## CloudPunch Prerequisites

The prerequisites for each role is as follows. Note that any tests run will probably have their own requirements. Please see individual test documentation for any additional requirements

- Local Machine
    - Python 2.7
    - PIP: flask, requests, tabulate, futures, pyyaml, python-keystoneclient, python-novaclient, python-neutronclient, python-cinderclient, python-glanceclient, python-swiftclient, plotly
    - Packages: none


- Worker (OpenStack image)
    - Python 2.7
    - PIP: xmltodict, gunicorn, kafka
    - Packages: none

The OpenStack image used should contain all required software for the best staging time. If the image is missing software, the `shared_userdata` and `userdata` keys for respective roles will have to contain the commands required to install the missing software. The CloudPunch software must be install as the `cloudpunch` command

##### Why?

- Python 2.7 - written only for 2.7 support. Currently 3.0 is not supported


- PIP
    - tabulate - prints out environment details during run
    - futures - handles instance creation threading
    - pyyaml - allows use of YAML files
    - python-keystoneclient - handles interaction with OpenStack keystone
    - python-novaclient - handles interaction with OpenStack nova
    - python-neutronclient - handles interaction with OpenStack neutron
    - python-cinderclient - handles interaction with OpenStack cinder
    - python-glanceclient - handles interaction with OpenStack glance
    - python-swiftclient - handles interaction with OpenStack swift
    - plotly - graphs over time results
    - flask - runs control server's API
    - requests - handles API calls to control server
    - xmltodict - modifies the jmeter XML file
    - gunicorn - runs as a web server for jmeter tests
    - kafka - sends test metrics to Kafka

## CloudPunch Installation

~~[PIP Installation](./getting_started_pip.md) (recommended)~~

[Docker Installation](./getting_started_docker.md) (ready-to-go container)

[Git Installation](./getting_started_git.md) (for development or local installation)

## CloudPunch Setup

CloudPunch is designed to be dynamic enough to work in any OpenStack environment. There are many options that can be changed to fit the needs of the environment. This section will go over a basic setup of CloudPunch and running a simple ping test.

### Creating Configuration

CloudPunch uses a JSON or YAML file to determine the overall configuration. See [Configuration File](./configuration.md#configuration-file) for more in-depth information about this file. Create a file named `config.yaml` with the following contents:

```yaml
cleanup_resources: true
server_client_mode: true
servers_give_results: true
overtime_results: false
instance_threads: 5
retry_count: 30
network_mode: full
number_routers: 2
networks_per_router: 2
instances_per_network: 2
test:
  - ping
test_mode: concurrent
ping:
  duration: 5
```

This configuration file will run the test ping for a duration of 5 seconds. It will create 2 routers with 2 networks each and 2 instances for each network (for a total of 6 instances). It will double these resource numbers because both servers and clients will be built. Both servers and clients will give results back. 5 instances will be created at a time with a max timeout of 30 retries. The results will be a summary rather than overtime. Finally, the resources will be deleted at the end of the test.

### Creating Environment

The environment file is also a JSON or YAML file but instead is used to determine values that change based on the OpenStack environment. These values will change greatly for each OpenStack setup. See [Environment Files](./configuration.md#environment-files) for more in-depth information about this file. Create a file named `environment.yaml` with the following contents:

```yaml
image_name: CentOS-7
server:
  flavor: m1.small
client:
  flavor: m1.small
```

This assumes that the image CentOS-7 and the m1.small flavor exists on the OpenStack environment. Note that this is a very basic environment file and will not be able to run a test without a custom OpenStack image.

### Creating OpenStack Image

It is required to create a custom OpenStack image containing all required software to run the framework. The CloudPunch team does **not** provide any image and is the responsibility of the user to create their own. See [CloudPunch Prerequisites](./getting_started.md#cloudpunch-prerequisites) for the minimum software required.

##### Sample Packer Creation

Packer provides a simple way of creating OpenStack images. See [here](https://www.packer.io/docs/) for the official Packer documentation. Packer will use an existing OpenStack image, run provisioners on it, then save that new image for use.

The following is a sample Packer configuration to create a base CloudPunch image. This configuration is designed to use the [CentOS-7-x86_64-GenericCloud.qcow2](http://cloud.centos.org/centos/7/images/CentOS-7-x86_64-GenericCloud.qcow2) image provided by the CentOS org.  This image must be uploaded to the OpenStack environment using glance. See [here](http://docs.openstack.org/user-guide/common/cli-manage-images.html) for documentation on creating images with glance. The image ID must be put in the packer configuration under `image_id`.

```json
{
    "builders": [{
        "type": "openstack",
        "ssh_username": "centos",
        "image_name": "cloudpunch",
        "source_image": "PUT IMAGE ID HERE",
        "flavor": "m1.small",
        "user_data": "#cloud-config\n\nruncmd:\n - sed -i '/Defaults    requiretty/d' /etc/sudoers\n"
    }],
    "provisioners": [{
        "type": "shell",
        "script": "build-cloudpunch.sh"
    }]
}
```

```bash
#!/bin/bash

# Update image
sudo yum clean all
sudo yum update -y

# Install packages
curl -O https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
sudo yum install epel-release-latest-7.noarch.rpm
sudo yum-config-manager --enable epel
sudo yum install -y gcc make gcc-c++ python-pip python-devel libaio librados2 librados2-devel librbd1 librbd1-devel iperf3 fio jq

# Install jmeter
sudo yum install -y java-1.8.0-openjdk
sudo mkdir -p /opt
curl -s http://www.gtlib.gatech.edu/pub/apache//jmeter/binaries/apache-jmeter-3.1.tgz > /tmp/jmeter.tar.gz
sudo tar -zx -f /tmp/jmeter.tar.gz -C /opt
sudo ln -s /opt/apache-jmeter-3.1/bin/jmeter /usr/bin/jmeter

# Install stress-ng
curl -s http://kernel.ubuntu.com/~cking/tarballs/stress-ng/stress-ng-0.07.27.tar.gz > /tmp/stress-ng.tar.gz
tar -zx -f /tmp/stress-ng.tar.gz -C /tmp
cd /tmp/stress-ng-0.07.27/ || exit
sudo make
sudo make install

# Install CloudPunch
sudo mkdir -p /opt/cloudpunch
git clone https://github.com/target/cloudpunch.git /opt/cloudpunch
cd /opt/cloudpunch || exit
sudo pip install --upgrade pip
sudo pip install -r requirements.txt
sudo python setup.py install

```

## Running CloudPunch

After both the configuration and environment files are made, tests can now be run. It is recommended to source the OpenStack OpenRC file instead of using the `-r` option on the command-line. See [Command-line Options](./configuration.md#command-line-options) for a full list of command-line options. After sourcing the OpenRC file you can run CloudPunch

```
cloudpunch run -c config.yaml -e environment.yaml
```
