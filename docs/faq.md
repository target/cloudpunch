# Frequently Asked Questions

### Q: What is CloudPunch?

CloudPunch is a framework written in Python that is used to gauge the performance OpenStack clients will experience. It allows performance tests to be run across many instances at the same time and send all tests results back to the local machine. Because CloudPunch focuses on being a framework, there is a possibility of having a large amount of setup including creating tests that run desired software and returning needed results.

CloudPunch should be used to test the performance of instances running on OpenStack; it is not designed to test the performance of the OpenStack API. This data can be used to find bottlenecks and perform tweaks on the OpenStack environment. For example, iPerf3 could be used to find neutron bottlenecks.

### Q: What cloud platforms does CloudPunch support?

CloudPunch currently only supports OpenStack. There are no plans at this time to support more platforms.

### Q: Is there a image I can use with CloudPunch?

The CloudPunch team does not provide an OpenStack image. However, there is a sample Packer configuration to create a base image. See [Creating OpenStack Image](./getting_started.md#creating-openstack-image) for the sample configuration.
