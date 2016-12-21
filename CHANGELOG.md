# Change Log
A list of notable changes will be documented here

## 1.2.0 - 2016-12-21
### Added
- Ability to have instances boot from volume (see environment file)
- FIO test now supports FIO test files

### Changed
- iPerf test no longer has an enable field to avoid confusion

## 1.1.1 - 2016-11-18
### Changed
- Now wait a max of 5 seconds before detaching a router interface is marked as a failure to prevent delays in neutron causing errors
- Only use the master's floating IP address when using network-mode 'full'. This allows slaves to connect to the master without the need for SNAT

## 1.1.0 - 2016-10-17
### Added
- Test results now return errors to the master if the run fails
- Left over resources after a cleanup will now be added to the cleanup file. This includes items that failed to delete
- Post cleanup now supports the insecure flag
- Post cleanup now supports multiple OpenStack API versions. The cleanup file will now include the versions for cinder, nova, and neutron
- A simple post processor for test results has been added. Run either `cloudpunch-post` or `cloudpunch/post.py`. Currently it only displays totals and averages of all instance results

### Changed
- Overtime results for fio and iperf no longer give the raw results from the process. The overtime results now match what the summary results give back
- Reuse mode no longer overwrites the output file. Now, a number will be added to subsequent tests. For example: results.json, results-1.json, results-2.json.
- Post cleanup will now ignore missing resources
- Post cleanup will now update the cleanup file if it fails to delete resources

## 1.0.0 - 2016-09-27
### Added
- Initial release
