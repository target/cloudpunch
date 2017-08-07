# Change Log
A list of notable changes will be documented here

## 1.5.0 - 2017-xx-xx
### Added
- New configuration options in the jmeter test. You can now specify `port` and `path` when connecting to a server
- New `graph` format option in cloudpunch post. This option uses plotly to graph results into an HTML file

### Changed
- Fixed incorrect overtime results in the FIO test
- stress-ng test now supports summary results
- ping test no longer includes target

## 1.4.0 - 2017-06-14
### Added
- Cleanup now has the flag `-n, --dry-run` when performing a search. This will prevent resources from being deleted
- Cleanup now has the flag `-a, --names` when performing a search. It will print out the UUIDs and names of found resources

### Changed
- The SSH public key file specified in the environment file is now checked if it exists
- Security groups are now made through Neutron instead of Nova (deprecated in novaclient 8)
- Images are now searched inside Glance instead of Nova (deprecated in novaclient 9)
- Cleanup will now only stay within the sourced project when an admin user
- Cleanup will now not list out repeated neutron resources

## 1.3.1 - 2017-05-01
### Added
- availability_zone is now an option under server and client volume

### Changed
- Babel is now pinned to version 2.3.4 to avoid dependency issues

## 1.3.0 - 2017-04-20
### Added
- Load balancer support in front of servers and/or clients. See Configuration documentation for more information
- Custom test files can now be added into a `tests/` directory inside the current working directory. Any test files inside the configuration will be pushed over to the slaves to run
- cloudpunch post now supports formatting results to json, yaml, table, and csv
- cloudpunch post now calculates mean, median, mode, range, and total instead of just mean and total
- cloudpunch cleanup can now search for resources left over by previous cloudpunch runs. Use `cloudpunch cleanup search`

### Changed
- cloudpunch-cleanup and cloudpunch-post have now been integrated into the main cloudpunch command. To run a test use cloudpunch run, to cleanup use cloudpunch cleanup, and to post process use cloudpunch post
- cloudpunch-master and cloudpunch-slave have also been integrated into the main cloudpunch command. Use cloudpunch master to start the master and cloudpunch slave to start a slave
- All official tests now have a default configuration

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
