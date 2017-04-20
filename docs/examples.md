# Examples

This section goes over examples that cover more specific scenarios that are possible with CloudPunch. These are to be used as a starting point.

## Processing Results

CloudPunch does not include a GUI and returns results in a JSON or YAML format. The results are listed out by hostname then by test. In many cases the results needed are simply a total or an average of all host results. CloudPunch includes a simple post processor to display averages and totals from result files.

I have run a test that included iPerf and ping tests. The test was configured to run many instances. I only care about the totals and averages of the results given by each instance. The results were saved to the file `networkping.json` using the `-o` option on the CloudPunch CLI.

```
cloudpunch post networkping.json

2016-10-03 15:03:29 INFO Converted results:
iperf:
  averages:
    bps: 2.58 Gbps
    retransmits: 60
  totals:
    bps: 129.06 Gbps
    retransmits: 3.02 K
ping:
  averages:
    duration: 360.0
    latency: 5.81
  totals:
    duration: 18000.0
    latency: 290.52
```

## Using Loadbalancers with CloudPunch

CloudPunch supports the creation of loadbalancers (both v1 and v2) in front of servers and/or clients. The loadbalancers are added on each network created. They will use fixed IP addresses on network modes single-network and single-router and use floating IP addresses on the network mode full. To enable the use of loadbalancers add the following to the environment file:

```yaml
server:
  loadbalancer:
    enable: true
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
      retries: 3
```

This will enable the creation of loadbalancers in front of servers. The loadbalancer will use the algorithm ROUND_ROBIN and listen for HTTP on port 80 and forward to HTTP on port 80. The health monitor will use ping every 5 seconds and mark a server as inactive after 3 failed pings.

## Using Volumes with CloudPunch

CloudPunch supports creating cinder volumes and mounting them to instances for testing. CloudPunch does not format or mount these volumes and it is recommended to put these commands into userdata.

I want to run an FIO test on a mounted cinder volume. To have CloudPunch create a cinder volume and mount it to a server add the following configuration to the environment file:

```yaml
server:
  volume:
    enable: true
    size: 20
    type:
```

This will mount a 20 Gigabyte volume to each server role instance. This volume is mounted at `/dev/vdb`.

To format and mount this volume add the following configuration to the environment file:

```yaml
server:
  userdata:
    - mkfs -t ext4 /dev/vdb
    - mkdir /osperf
    - mount /dev/vdb /osperf
```

This will format `/dev/vdb` to use ext4 and mount the volume to `/osperf`. Make sure the FIO configuration points to this directory in the configuration file like so:

```yaml
fio:
  filename: /osperf/fiotest
```

## Tests on Specific OpenStack Hosts

To determine where instances will be created use a hostmap file. See [Hostmap Files](./configuration.md#hostmap-files) for in-depth documentation.

I have 3 compute hosts that can host OpenStack instances called compute1, compute2, compute3. I want each to be labeled as zoneN where N is the compute number. I want compute 1 to go to compute 2, compute 2 to go to 3, and compute 3 to go to 1. I am making 10 servers and 10 clients. Using the following hostmap file:

```yaml
tags:
  zone1: 'host:compute1'
  zone2: 'host:compute2'
  zone3: 'host:compute3'
map:
  - zone1,zone2
  - zone2,zone3
  - zone3,zone1

```

The 10 servers and 10 clients will be hosted as follows:

| Server # | Host     | Client # | Host     |
| :------: | -------- | :------: | -------- |
| 1        | compute1 | 1        | compute2 |
| 2        | compute2 | 2        | compute3 |
| 3        | compute3 | 3        | compute1 |
| 4        | compute1 | 4        | compute2 |
| 5        | compute2 | 5        | compute3 |
| 6        | compute3 | 6        | compute1 |
| 7        | compute1 | 7        | compute2 |
| 8        | compute2 | 8        | compute3 |
| 9        | compute3 | 9        | compute1 |
| 10       | compute1 | 10       | compute2 |

## Varying Flavor Use

To use a varying amount of flavors rather than one flavor per role use a flavor file. See [Flavor Files](./configuration.md#flavor-files) for in-depth documentation. The flavor file works off percentage of total instances. The flavors are applied for both servers and clients.

I have 5 servers with the following flavor file:

```yaml
flavors:
  m1.tiny: 0
  m1.demo: 0
  m1.small: 50
  m1.medium: 50
  m1.large: 0
  m1.xlarge: 0
```

The servers will have the following flavors assigned to them:

| Server # | Flavor    |
| :------: | --------- |
| 1        | m1.small  |
| 2        | m1.small  |
| 3        | m1.medium |
| 4        | m1.medium |
| 5        | m1.medium |

Notice that server 3 is assigned m1.medium rather than m1.small. This is because 3 of 5 is greater than 50%. Server 5 is given the last flavor in the list, m1.medium.

## Manually Starting

To manually start a test use the `--manual` command-line option. After staging the environment and waiting for all instances to register you will be prompted:

```
2016-08-04 13:18:08 INFO All instances registered
2016-08-04 13:18:08 INFO Sent configuration to master
Press enter to start test
```

Simply hit Enter and the test will begin.

## Reusing Instances

To reuse the environment setup by CloudPunch use the `--reuse` command-line option. After the test completes you will be prompted:

```
2016-08-04 13:21:50 INFO All instances have posted results
2016-08-04 13:21:50 INFO Got results from master
2016-08-04 13:21:50 INFO Results:
[{"hostname": "CloudPunch-7855343-master-s1", "results": {"ping": {"duration": 5, "latency": 12.7, "target": "google.com"}}}]
Enter new test type (same, different, abort)
```

Entering same will rerun the test, different will prompt for a new configuration file, and abort will tear down the environment.

## Tests Across Environments

CloudPunch supports testing across OpenStack environments or regions. The setup is the same for both scenarios. To do this simply add the following to the command-line:

- `-r2` - The second environment or region OpenRC file.
- `-e2` - The second environment or region environment file. This is optional. If not given, the environment file given by `-e` will be used.
- `--split` - Enables split mode which allows tests to run across environments or regions.

The master instance will be created on environment or region 1 with servers while environment or region 2 will contain clients.

## Post Test Cleanup of Resources

By default CloudPunch will cleanup resources when completed. However if cases where troubleshooting is needed or to run a test without keeping a connection alive to the master instance, you can disable this feature. Add the following to the configuration file:

```yaml
cleanup_resources: false
```

When disabled a cleanup file will instead be created that contains all the IDs of resources created. Run `cloudpunch cleanup cleanup-file.json`

## Recovery from Unregistered Instances

CloudPunch has the ability to rebuild unregistered instances if they take too long to register. This can be used to recover from a couple instances taking too long. To use recovery mode add the following to the config file:

```yaml
recovery:
  enable: true
  type: rebuild
  threshold: 80
  retries: 20
```

The threshold refers to how many instances are registered versus the total number. This is in a percentage so the above example would be 80% registered. Retries refers to how many retries before recovery should take place. When a recovery takes place the unregistered instances will be deleted and recreated. Note that recovery can happen indefinitely. By design there is no way to ignore unregistered instances and continue on with a test.
