# Configuration Options

All CloudPunch configuration is given through the command-line

## Command-line Options

The following options are given on the command-line when using cloudpunch

- `workload` - The type of workload to run. Can be run, cleanup, post, or worker. These are covered below

- `-h, --help` - Show the help message and exit

- `-v, --version` - Show the version number and exit

- `-l, --loglevel` - Specify a log level when the default of INFO is not wanted. The following log levels are valid: DEBUG, INFO, WARNING, ERROR, and CRITICAL

- `-L, --logfile` - Specify a log file to send all logging to rather than `stdout`. Note that this will overwrite any file given and **not** append

## Run Command-line Options

The following options are given on the command-line when using cloudpunch run

- `-c, --config` - Provide a JSON formatted configuration file that will override the default configuration. Any keys that are missing will use the default values. See Configuration Files below for more information

- `-e, --env` - Provide a JSON formatted environment file that will override the default environment configuration. Any keys that are missing will use the default values. See Environment Files below for more information

- `-e2, --env2` - Environment file used for the second OpenStack instance if `--split` is used

- `-r, --openrc` - Provide an OpenRC file containing authentication information for OpenStack. Note that information in the environment will override anything in the OpenRC file

- `-r2, --openrc2`- OpenRC file for second OpenStack instance if `--split` is used

- `-m, --hostmap` - Provide a hostmap file to determine where each instance created will be hosted on. See Hostmap Files below for more information

- `-b, --flavor` - Provide a flavor file to determine the percentage of instances with specific flavors. This will override any flavor configuration. See Flavor Files below for more information

- `-o, --output` - Specify an output file to save results to. Results will be printed to `stdout` if an output file is not specified

- `-f, --format` - Format the results into the specified format. Can be yaml or json with yaml being the default

- `-p, --password` - Provide a password or token to authenticate to OpenStack. This should only be used when in a non-interactive environment and the environment does not contain the password or token

- `-p2, --password2` - Password for second OpenStack instance if `--split` is used

- `-i, --reuse` - Enable reuse mode by providing an existing CloudPunch run ID. This will reuse any resources that belong to this ID and adjust the environment to match the new configuration

- `-l, --listen` - Local address that the control server will bind to. The default is 0.0.0.0

- `-t, --port` - Local port that the control server will bind to. The default is 9985. This will populate down to the worker servers

- `-w, --connect` - Provide a local interface or IP address as a hint to what the worker servers on OpenStack will connect back to when communicating with the local control server. By default CloudPunch will attempt to find an IP address based on the default gateway of the local machine. Note that this does not have to be a known IP address or DNS name from the local machine (for example: a floating IP address on OpenStack)

- `--no-env` - Disables loading authentication information from the environment. Use this to force the OpenRC file over the environment

- `--manual` - Enable manual test start mode. After the environment is staged and ready but before the test begins, the user must press Enter to continue. Note that this requires interactive

- `--insecure` - Turn off SSL verification to the OpenStack API's

## Cleanup Command-line Options

The following options are given on the command-line when using cloudpunch cleanup

- `cleanup_file` - Provide the cleanup file containing all resource IDs. This cleanup file is created when CloudPunch terminates. This can be 'search' to search for resources that have been left over

- `-r, --openrc` - Provide an OpenRC file containing authentication information for OpenStack. Note that information in the environment will override anything in the OpenRC file

- `-p, --password` - Provide a password to authenticate to OpenStack. This should only be used when in a non-interactive environment and the environment does not contain the password

- `-n, --dry-run` - Do not delete after searching for resources

- `-a, --names` - Show names and UUIDs of found resources

- `--no-env` - Disables loading authentication information from the environment. Use this to force the OpenRC file over the environment

- `--insecure` - Turn off SSL verification to the OpenStack API's

## Post Command-line Options

The following options are given on the command-line when using cloudpunch post

- `results_file` - Provide the results file from a CloudPunch run

- `-f, --format` - The format to convert the processed results to. Can be json, yaml (default), table, or csv

- `o, --output` - Specify an output file to save processed results to

- `-s, --stat` - Stat from test to graph (graph format only)

- `-t, --test` - Name of the CloudPunch test to graph (graph format only). By default all tests will be graphed

- `-j, --job` - Name of the FIO job to graph (FIO test and graph format only)

- `--summary` - Convert over time results to summary results

- `--raw` - Do not convert numbers to human readable format. By default 3000 would be converted to 3 K

- `--open` - Open the generated HTML graph file after creation (graph format only)

## Worker Command-line Options

The following options are given on the command-line when using cloudpunch worker

- `control_ip` - IP address of the control server

- `-p, --port` - Port of the control server. The default is 9985

## Configuration File

The configuration is a JSON or YAML formatted file containing information needed to run CloudPunch and is provided using the `-c` command-line option. Default values will be used if keys are missing from the file. The configuration file is exposed to the tests running and often will contain extra information needed by the specific test. See the documentation for the specific test for information on what extra keys are required.

##### Default Configuration

```yaml
cleanup_resources: true
server_client_mode: true
servers_give_results: true
overtime_results: false
instance_threads: 5
retry_count: 50
network_mode: full
number_routers: 1
networks_per_router: 1
instances_per_network: 1
test:
  - ping
test_mode: list
test_start_delay: 0
recovery:
  enable: false
  type: ask
  threshold: 80
  retries: 12
metrics:
  enable: false
  topic:
  brokers: []
  format: influxdb
  tags: {}
```

##### Configuration Key Reference

- `cleanup_resources` - If resources should be deleted at the end of the process. This is on all cases including if an error occurs. If `false`, a cleanup file will be created in the current directory. This cleanup file is used with `cleanup.py` to delete the environment at a later time

- `server_client_mode` - If the test requires that there is a server and a client. This will double the number of routers, networks, and instances created. The `role` key is used inside tests to know if an instance is server or client. The default role is server

- `servers_give_results` - If the role of server gives results to the test. Note that this is ignored if `server_client_mode` is disabled. This option also includes if clients give results as it only causes the number of instances expected to give results to be half of the total number of instances

- `overtime_results` - If the results given from tests should be overtime or a summary. For example, should iperf give results every interval or should it give an average bps for the whole test. Note that tests will have to implement this configuration

- `instance_threads` - How many instances should be created at the same time. Adjust this number based on the power of the OpenStack environment

- `retry_count` - Number of retries done before a process is considered a failure. This is used during creation and connecting to instances

- `network_mode` - The type of network setup for the instances. The following options are allowed:

  - "full" - Create routers, networks, and instances with floating IP addresses

  - "single-router" - Create networks and instances without floating IP addresses. All networks will be connected to the master router and use internal IP addresses to communicate. Note that this requires SNAT

  - "single-network" - Create instances with floating IP addresses. All instances will be connected to the master network and use internal IP addresses to communicate. Note that this requires SNAT

- `number_routers` - The number of routers to be created. This is only used if `network_mode` is "full"

- `networks_per_router` - The number of networks to be created for each router. This is ignored if `network_mode` is "single-network"

- `instances_per_network` - The number of instances to be created for each network

- `test` - A list of test names to run. These test names are derived from the filenames inside `worker/`. For example `iperf.py` would be "iperf"

- `test_mode` - The type of test processing that should occur. The following options are allowed:

  - "list" - Run the tests in order where only one runs at a time

  - "concurrent" - Run the tests at the same time

- `test_start_delay` - Number of seconds to wait before a test starts. If `test_mode` is "list" the delay will be applied before the start of each test. For example: wait, test, wait, test. If `test_mode` is "concurrent" the delay will be applied only before the initial start. For example: wait, all tests

- `recovery` - Used to recover the environment if instance registration takes too long. `recovery` has the following sub keys:

  - `enable` - If to enable recovery mode

  - `type` - The type of recovery mode. The following options are allowed:

    - "ask" - The user will be asked what type of recovery should happen. Rebuild (delete and recreate instances), Abort (tear down environment), or Ignore (continue on with registration)

    - "rebuild" - Delete and recreate unregistered instances

  - `threshold` - The percent of instances that are required to be registered for a recovery to take place

  - `retries` - The number of retries before a recovery is to take place. If the threshold is not passed, recovery will be ignored

- `metrics` - Used to send test metrics to Kafka while tests are running. `metrics` has the following sub keys:

  - `enable` - If to enable sending metrics

  - `topic` - Name of the Kafka topic to send messages to

  - `brokers` - A list of Kafka brokers to connect to

  - `format` - The format of the messages sent to Kafka. Currently only influxdb is supported

  - `tags` - A dictionary of tags to add to all metrics sent to Kafka

## Environment Files

The environment is a JSON or YAML formatted file containing information needed to run CloudPunch in specific environments and is provided using the `-e` command-line option. Default values will be used if keys are missing from the file

##### Default Environment

```yaml
image_name: CentOS7
public_key_file: ~/.ssh/id_rsa.pub
api_versions:
  cinder: 2
  glance: 2
  nova: 2
  neutron: 2
  lbaas: 2
server:
  flavor: m1.small
  availability_zone:
  volume:
    enable: false
    size: 10
    type:
    availability_zone:
  boot_from_vol:
    enable: false
    size: 10
  loadbalancer:
    enable: false
    method: ROUND_ROBIN
    frontend:
      protocol: HTTP
      port: 80
    backend:
      protocol: HTTP
      port: 80
    healthmonitor:
      type: PING
      delay: 5
      timeout: 5
      retires: 3
      url_path: /
      http_method: GET
      expected_codes: "200"
  userdata:
client:
  flavor: m1.small
  availability_zone:
  volume:
    enable: false
    size: 10
    type:
    availability_zone:
  boot_from_vol:
    enable: false
    size: 10
  loadbalancer:
    enable: false
    method: ROUND_ROBIN
    frontend:
      protocol: HTTP
      port: 80
    backend:
      protocol: HTTP
      port: 80
    healthmonitor:
      type: PING
      delay: 5
      timeout: 5
      retires: 3
      url_path: /
      http_method: GET
      expected_codes: "200"
  userdata:
secgroup_rules:
  - - icmp
    - -1
    - -1
  - - tcp
    - 22
    - 22
  - - tcp
    - 5201
    - 5201
dns_nameservers:
  - 8.8.8.8
  - 8.8.4.4
shared_userdata:
  - mkdir -p /opt/cloudpunch
  - git clone https://github.com/target/cloudpunch.git /opt/cloudpunch
  - cd /opt/cloudpunch
  - python setup.py install
external_network:
```

##### Environment Key Reference

- `image_name` - The OpenStack image name used when creating all instances. This can be a name or ID

- `public_key_file` - Path to the public key to use when creating a keypair. This is used to allow SSH access for troubleshooting purposes

- `api_versions` - The OpenStack API versions to use when creating and deleting resources. Note that the Keystone version is determined by authentication parameters. `api_versions` has the following sub keys:

  - `cinder` - The version of cinder (storage) to use

  - `nova` - The version of nova (compute) to use

  - `neutron` - The version of neutron (network) to use

  - `lbaas` - The version of lbaas (loadbalancer as a service) to use

- `server` - Properties that apply to the server role. The server role is a worker that is designated as a server during creation and when tests are running. `server` has the following sub keys:

  - `flavor` - The name of the flavor to use when creating the instance. This must be the name and not an ID

  - `availability_zone` - The availability zone to attach the server role to

  - `volume` - Properties that apply to an attached cinder volume. Note that CloudPunch does not format the volume and it is recommended to use userdata to format and mount the volume. `volume` has the following sub keys:

      - `enable` - If a volume should be created and attached

      - `size` - The size of the volume in Gigabytes

      - `type` - The type of the volume. This is not required

      - `availability_zone` - The availability zone of the volume. This is not required

  - `boot_from_vol` - Properties that apply to booting from a volume rather than a local storage. `boot_from_vol` has the following sub keys:

      - `enable` - If the instance should boot from a volume rather than local storage

      - `size` - The size of the volume in Gigabytes

  - `loadbalancer` - Properties that apply to incorporating a loadbalancer in front of servers. `loadbalancer` has the following sub keys:

      - `enable` - If to enable the loadbalancer creation

      - `method` - The loadbalancer algorithm. Valid options are ROUND_ROBIN, LEAST_CONNECTIONS, or SOURCE_IP

      - `frontend` - Properties that apply to the frontend of the loadbalancer. `frontend` has the following sub keys:

          - `protocol` - Type of traffic protocol. Valid options are HTTP, HTTPS, or TCP

          - `port` - The protocol port

      - `backend` - Properties that apply to the backend of the loadbalancer. `backend` has the following sub keys:

          - `protocol` - Type of traffic protocol. Valid options are HTTP, HTTPS, or TCP

          - `port` - The protocol port

      - `healthmonitor` - Properties that apply to the loadbalancer's health monitor

          - `type` - The health monitor type. Valid options are PING, TCP, HTTP or HTTPS

          - `delay` - The delay between checks in seconds

          - `timeout` - The timeout period in seconds

          - `retires` - The maximum number of retries before a member is removed. Must be between 1 and 10

          - `url_path` - The url path to test. Only valid with HTTP or HTTPS types

          - `http_method` - The HTTP method to use to test. Only valid with HTTP or HTTPS types

          - `expected_codes` - A single (200), range (200-202), or comma-seperated (200,201,202) list of codes to consider valid

  - `userdata` - A list of commands processed by shell to run during the cloud-init process. This is used to setup the server role for specific environments and tests

- `client` - Properties that apply to the client role. The client role is a worker that is designated as a client during creation and when tests are running. `client` has the following sub keys:

  - `flavor` - The name of the flavor to use when creating the instance. This must be the name and not an ID

  - `availability_zone` - The availability zone to attach the client role to

  - `volume` - Properties that apply to an attached cinder volume. Note that CloudPunch does not format the volume and it is recommended to use userdata to format and mount the volume. `volume` has the following sub keys:

      - `enable` - If a volume should be created and attached

      - `size` - The size of the volume in Gigabytes

      - `type` - The type of the volume. This is not required

      - `availability_zone` - The availability zone of the volume. This is not required

  - `boot_from_vol` - Properties that apply to booting from a volume rather than a local storage. `boot_from_vol` has the following sub keys:

      - `enable` - If the instance should boot from a volume rather than local storage

      - `size` - The size of the volume in Gigabytes

  - `loadbalancer` - Properties that apply to incorporating a loadbalancer in front of clients. `loadbalancer` has the following sub keys:

      - `enable` - If to enable the loadbalancer creation

      - `method` - The loadbalancer algorithm. Valid options are ROUND_ROBIN, LEAST_CONNECTIONS, or SOURCE_IP

      - `frontend` - Properties that apply to the frontend of the loadbalancer. `frontend` has the following sub keys:

          - `protocol` - Type of traffic protocol. Valid options are HTTP, HTTPS, or TCP

          - `port` - The protocol port

      - `backend` - Properties that apply to the backend of the loadbalancer. `backend` has the following sub keys:

          - `protocol` - Type of traffic protocol. Valid options are HTTP, HTTPS, or TCP

          - `port` - The protocol port

      - `healthmonitor` - Properties that apply to the loadbalancer's health monitor

          - `type` - The health monitor type. Valid options are PING, TCP, HTTP or HTTPS

          - `delay` - The delay between checks in seconds

          - `timeout` - The timeout period in seconds

          - `retires` - The maximum number of retries before a member is removed. Must be between 1 and 10

          - `url_path` - The url path to test. Only valid with HTTP or HTTPS types

          - `http_method` - The HTTP method to use to test. Only valid with HTTP or HTTPS types

          - `expected_codes` - A single (200), range (200-202), or comma-seperated (200,201,202) list of codes to consider valid

  - `userdata` - A list of commands processed by shell to run during the cloud-init process. This is used to setup the client role for specific environments and tests

- `secgroup_rules` - A list of security group rules that will be attached to all instances created. Each rule is a list containing protocol, from port, and to port. For example: `["icmp", -1, -1]`

- `dns_nameservers` - A list of DNS nameservers that will be added to all subnets created

- `shared_userdata` - A list of commands processed by shell to run during the cloud-init process. This is added **before** each others userdata

- `external_network` - The name of the external network to connect routers and assign floating IP addresses from. If no name is given, the first result from the list of external networks will be used


## Hostmap Files

The hostmap is a JSON or YAML formatted file containing a list of availability zones or hosts that will determine where each instances will land. Note that when using a hostmap, the `availability_zone` keys for servers and clients will be ignored. The master key will not be ignored. It consists of two main keys: `tags` and `map`. `tags` is used to translate something in the map to it's real name. For example `compute-zone1` could be tagged as `zone1`. The `map` key is a list of availability zones or tags. Each entry has two comma separated availability zones or tags. The first is where the server will end up and the second is where the client will end up. This pair of server and client will be associated with each other later on for tests. This list is processed in order of creation and if the list is exhausted, it will begin at the beginning again.

##### Hostmap Example

```yaml
tags:
  zone1: compute-zone1
  zone2: compute-zone2
  zone3: compute-zone3
  zone4: compute-zone4
  zone5: compute-zone5
  zone6: compute-zone6
map:
  - zone1,zone2
  - zone2,zone3
  - zone3,zone4
  - zone4,zone5
  - zone5,zone6
  - zone6,zone1
```

## Flavor Files

The flavor file is a JSON or YAML formatted file containing a list of flavors assigned to a percentage. This will determine how many instances will be assigned a specific flavor. Note that when using a flavor file, the `flavor` keys for servers and clients will be ignore. The master key will not be ignored. If `server_client_mode` is enabled, both servers and clients will follow the flavor file the same way. Note that the percentages have to add up to be between 99% and 100%. This is to account for scenarios that are close to 100% but not exact such as 33.33% or 1/3.

##### Flavor File Example

```yaml
flavors:
  m1.tiny: 0
  m1.demo: 0
  m1.small: 50
  m1.medium: 50
  m1.large: 0
  m1.xlarge: 0
```
