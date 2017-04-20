# Docker Installation

This installation is recommended if familiar with Docker and an isolated environment is wanted

#### 1. Install Dependencies

See Docker documentation found [here](https://docs.docker.com/)

#### 2. Pull Latest Docker Image

```
docker pull <insert image name here>
```

#### 3. Run Docker Image

```
docker run -v $PWD:/opt/cloudpunch --rm -it <insert image name here> bash
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
