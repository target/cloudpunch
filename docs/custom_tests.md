# Writing Custom Tests

All tests live under `cp_slave/` as `testname.py`. The test name is set in the configuration file. See existing tests inside `cp_slave/` for further examples.

Tests must be located on the instances that run the tests. If a custom test is created it is recommended to tar ball the source code with the new test and host this tar ball so the instances can download said tar ball (by changing instance userdata).

##### Custom Test Example
```python
import os
import logging

from threading import Thread


class CloudPunchTest(Thread):

    def __init__(self, config):
        self.config = config
        self.final_results = 'NoData'
        super(CloudPunchTest, self).__init__()

    def run(self):
        if self.config['role'] == 'server' and 'server-command' in self.config:
            logging.info('Starting custom test with server command %s', self.config['server-command'])
            os.popen(self.config['server-command'])
        elif self.config['role'] == 'client' and 'client-command' in self.config:
            logging.info('Starting custom test with client command %s', self.config['client-command'])
            os.popen(self.config['client-command'])
        else:
            logging.error('Missing required command information')
```

A test must contain `CloudPunchTest` class as a `Thread` type. It must inherit from `Thread` because the slaves run the test classes as threads. The `__init__` must contain `config`. This is a dictionary representing the configuration file given. Be sure to include `super(CloudPunchTest, self).__init__()` to call the parent Thread's init method. The `run` method has no added arguments and is designed to run the actual test. Note that any custom keys added in the configuration file are exposed as seen with `self.config['server-command']`.

Any results are to be saved in `self.final_results`. This serves to allow the master to expose test results back to the local machine. Results should not be left empty. If a run is configured not to send results back the results will not be posted to the master instance. If there is no data to send back, set results to something such as `'NoData'` seen in the example above

Tests should be written to be run by servers and clients in case `server_client_mode` is enabled and a test should only be run by servers. This is because multiple tests can run in a single creation. These tests can be a mix of ones that require both server and client and ones that do not

There are extra keys are that injected into the configuration:

- `role` - The role of slave. Either `"server"` or `"client"`

- `match_ip` - The IP address of the associated instance to the slave
