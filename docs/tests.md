# CloudPunch Tests

Tests that live under `cloudpunch/slave` will be documented here.

## FIO

FIO is short for Flexible IO, a versatile IO workload generator. FIO is widely used as an industry standard benchmark, stress testing tool, and for IO verification purposes. See [here](http://linux.die.net/man/1/fio) for official FIO documentation

### Configuration

#### Test File

FIO supports a job file that contains all information needed to run a test. These job files can contain multiple jobs inside of it. See examples of job files [here](https://github.com/axboe/fio/tree/master/examples)

##### Static Configuration

The following are always put on the command line and cannot be changed:

```
--output-format=json
```

##### Sample Configuration

The following configuration will load in the file job.fio and run this file:

```yaml
fio:
  test_file: job.fio
```

#### Argument Based

FIO has many configuration flags and because of this the configuration keys provided will be directly injected into the command line options. For example: if `size` is set to `1G` in the configuration, the FIO command will have `--size=1G` added to it

##### Static Configuration

The following are always put on the command line and cannot be changed:

```
--name=fiotest --time_based --output-format=json
```

##### Default Configuration

The following configuration will translate into the following command line options:

```
--randrepeat=1 --ioengine=libaio --direct=1 --filename=/fiotest --bsrange=4k-8k --iodepth=8 --size=1G --readwrite=randrw --rwmixread=50 --numjobs=1 --status-interval=1 --runtime=300
```

```yaml
fio:
  randrepeat: 1
  ioengine: libaio
  direct: 1
  filename: /fiotest
  bsrange: 4k-8k
  iodepth: 8
  size: 1G
  readwrite: randrw
  rwmixread: 50
  numjobs: 1
  status-interval: 1
  runtime: 300
```

### Results

##### Overtime Results

```yaml
- hostname: cloudpunch-6924523-master-s1
  results:
    fio:
      fiotest:
        read:
          - latency_msec: 0.59629
            iops: 6518.19
            bandwidth_bytes: 26059
            total_bytes: 23636
            time: 1475079260
          - latency_msec: 0.6225
            iops: 6560.09
            bandwidth_bytes: 26213
            total_bytes: 23776
            time: 1475079260
        write:
          - latency_msec: 0.59629
            iops: 6518.19
            bandwidth_bytes: 26059
            total_bytes: 23636
            time: 1475079260
          - latency_msec: 0.6225
            iops: 6560.09
            bandwidth_bytes: 26213
            total_bytes: 23776
            time: 1475079260
```

##### Summary Results

```yaml
- hostname: cloudpunch-5454269-master-s1
  results:
    fio:
      fiotest:
        read:
          latency_msec: 97.28486333333333
          iops: 43.309999999999995
          bandwidth_bytes: 166000
          total_bytes: 1848000
        write:
          latency_msec: 76.62147999999999
          iops: 36.88666666666667
          bandwidth_bytes: 144000
          total_bytes: 1620000
```

### Post Processing

##### Graph Stats

The following is a mapping of test results to the graph format stats. Use these stats with the `-s` option on cloudpunch post  when using `-f graph`

| Stat Name | Results Name    | Graph Label                               |
| --------- | --------------- | ----------------------------------------- |
| iops      | iops            | Input/Output Operations per Second (IOPS) |
| latency   | latency_msec    | Latency (msec)                            |
| bandwidth | bandwidth_bytes | Bandwidth (Bps)                           |
| bytes     | total_bytes     | Total Bytes                               |

## iPerf3

iPerf3 is used for network throughput testing. See [here](https://iperf.fr/iperf-doc.php) for the official iPerf3 documentation.

#### Server vs Client

iPerf3 will be run as the role of the instance. If the instance is a server role, it will be run as a server. If the instance is a client role, it will be run as a client.

### Server Configuration

The server role has no configuration

### Client Configuration

The client configuration is designed to run a random amount of bandwidth over a random amount of time.

##### Configuration Key Reference

- `target` - The target the iPerf3 client should connect to. This is only used when `server_client_mode` is `false`. If `server_client_mode` is `true`, the target is the corresponding server instance

- `bps_min` - The minimum number of megabits per second (Mbps) an iteration will do

- `bps_max` - The maximum number of megabits per second (Mbps) an iteration will do

- `duration_min` - The minimum duration of an iteration

- `duration_max` - The maximum duration of an iteration

- `iterations` - How many iterations should be run

- `threads` - How many threads iPerf3 will run

- `max_throughput` - If set to `true`, `bps_min` and `bps_max` will be ignored and instead iPerf3 will attempt to use as much network bandwidth as possible

- `mss` - The maximum segment size of packets. This is usually 1460 or 8960

##### Default Configuration

```yaml
iperf:
  bps_min: 100000
  bps_max: 100000000
  duration_min: 10
  duration_max: 30
  iterations: 10
  threads: 1
  max_throughput: true
  mss: 1460
```

### Results

##### Overtime Results

```yaml
- hostname: cloudpunch-8678796-master-c1
  results:
    iperf:
      - bps: 1241740000
        retransmits: 802
        time: 1475078878
      - bps: 1159130000
        retransmits: 207
        time: 1475078879
      - bps: 973007000
        retransmits: 227
        time: 1475078880
      - bps: 1236210000
        retransmits: 116
        time: 1475078881
      - bps: 1183880000
        retransmits: 411
        time: 1475078882
```

##### Summary Results

```yaml
- hostname: cloudpunch-9686117-master-c1
  results:
    iperf:
      bps: 63472446.666666664
      retransmits: 0
```

### Post Processing

##### Graph Stats

The following is a mapping of test results to the graph format stats. Use these stats with the `-s` option on cloudpunch post  when using `-f graph`

| Stat Name   | Results Name | Graph Label       |
| ----------- | ------------ | ----------------- |
| bps         | bps          | Throughput (Gbps) |
| retransmits | retransmits  | Retransmits       |

## Ping

Ping is used solely for latency testing. It often is used with iPerf3 to see how latency is affected by high network throughput.

### Configuration

Ping can be ran with `server_client_mode` enabled or disabled. If enabled ping will use the corresponding instance as its target. If disabled, the `target` key will be used

##### Configuration Key Reference

- `duration` - How long the ping test should run for

- `target` - Where pings should be sent

##### Default Configuration

```yaml
ping:
  target: google.com
  duration: 10
```

### Results

Latency is in msec

##### Overtime Results

```yaml
- hostname: cloudpunch-3693039-master-c1
  results:
    ping:
      - latency: 0.874
        time: 1470152735.793147
      - latency: 0.256
        time: 1470152736.792701
      - latency: 0.23
        time: 1470152737.793253
      - latency: 0.224
        time: 1470152738.792618
      - latency: 0.2
        time: 1470152739.792757
```

##### Summary Results

```yaml
- hostname: cloudpunch-3803825-master-c1
  results:
    ping:
      latency: 0.2032
```

### Post Processing

##### Graph Stats

The following is a mapping of test results to the graph format stats. Use these stats with the `-s` option on cloudpunch post  when using `-f graph`

| Stat Name   | Results Name | Graph Label       |
| ----------- | ------------ | ----------------- |
| latency     | latency      | Latency (msec)    |

## Stress-ng

Stress-ng is used for CPU usage tests. See [here](http://kernel.ubuntu.com/~cking/stress-ng/) for official documentation

### Configuration

The stress-ng configuration is designed to run a random amount of CPU usage over a random amount of time

##### Configuration Key Reference

- `nice` - Set a process priority for stress-ng. This can be used to not overload an instance completely

- `cpu-min` - The minimum number of CPU cores used for each iteration

- `cpu-max` - The maximum number of CPU cores used for each iteration

- `duration-min` - The minimum duration of each iteration

- `duration-max` - The maximum duration of each iteration

- `load-min` - The minimum percent of CPU load per iteration

- `load-max` - The maximum percent of CPU load per iteration

- `iteration` - How many iteration stress-ng will be ran

- `delay` - The time between each iteration in seconds

##### Default Configuration

```yaml
stress:
  nice: 0
  cpu-min: 1
  cpu-max: 2
  duration-min: 5
  duration-max: 10
  load-min: 25
  load-max: 90
  iterations: 5
  delay: 5
```

### Results

Stress-ng results are what random number stress-ng was assigned to run at each iteration

##### Overtime Results

```yaml
- hostname: cloudpunch-8547561-c-r1-n1-c8
  results:
    stress:
      - load: 69
        cpu: 1
        timeout: 5
      - load: 65
        cpu: 1
        timeout: 8
      - load: 64
        cpu: 1
        timeout: 5
      - load: 27
        cpu: 1
        timeout: 7
      - load: 53
        cpu: 2
        timeout: 5
```

##### Summary Results

```yaml
- hostname: cloudpunch-8547561-c-r1-n1-c8
  results:
    stress:
      load: 69
      cpu: 1
      timeout: 5
```

### Post Processing

##### Graph Stats

The following is a mapping of test results to the graph format stats. Use these stats with the `-s` option on cloudpunch post  when using `-f graph`

| Stat Name   | Results Name | Graph Label       |
| ----------- | ------------ | ----------------- |
| load        | load         | CPU Load          |
| cpu         | cpu          | CPU Count         |

## JMeter

Apache JMeter is a java-based application used to test web server load. See [here](https://jmeter.apache.org/) for official JMeter documentation

### Configuration

All configuration lives under the `jmeter` key inside the configuration file

#### Server Configuration

##### Server Configuration Key Reference

- `gunicorn` - Gunicorn is used as the web server to support proper multiprocessing. `gunicorn` has the following sub-keys:

  - `workers` - the number of workers. Gunicorn recommends (2 * number-of-cores) + 1 as a good starting point

  - `threads` - the number of threads per worker. It is recommended to use around 4 threads per worker

###### Default Server Configuration

```yaml
jmeter:
  gunicorn:
    workers: 5
    threads: 4
```

#### Client Configuration

##### Client Configuration Key Reference

- `target` - the IP address or hostname to connect to (this is only available without server_client_mode)

- `threads` - the number of threads to start for http requests

- `ramp-up` - the number of seconds for the threads to start

- `duration` - the number of seconds to run the test for

- `port` - the port to connect to

- `path` - the URL path to connect to

###### Default Client Configuration

```yaml
jmeter:
  threads: 10
  ramp-up: 0
  duration: 60
  port: 80
  path: /api/system/health
```

### Results

##### Overtime Results

```yaml
- hostname: cloudpunch-8153315-c-r2-n2-c2
  results:
    jmeter:
    - error_count: 0
      error_percent: 0.0
      latency_msec: 7
      requests_per_second: 1286.5
      time: 20
    - error_count: 0
      error_percent: 0.0
      latency_msec: 7
      requests_per_second: 1405.5
      time: 50
    - error_count: 0
      error_percent: 0.0
      latency_msec: 7
      requests_per_second: 1402.5
      time: 80
```

##### Summary Results

```yaml
- hostname: cloudpunch-5487841-c-master-n1-c1
  results:
    jmeter:
      error_count: 2405
      error_percent: 2.07
      latency_msec: 15
      requests-per-second: 1937.7
```

### Post Processing

##### Graph Stats

The following is a mapping of test results to the graph format stats. Use these stats with the `-s` option on cloudpunch post when using `-f graph`

| Stat Name   | Results Name        | Graph Label         |
| ----------- | ------------------- | ------------------- |
| requests    | requests_per_second | Requests per Second |
| ecount      | error_count         | Error Count         |
| epercent    | error_percent       | Error Percent       |
| latency     | latency_msec        | Latency (msec)      |
