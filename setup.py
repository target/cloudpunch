import sys
import os

from setuptools import setup

if not sys.version_info[0] == 2:
    sys.exit('Requires Python 2')


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(name='cloudpunch',
      version=read('docs/version'),
      description='Framework for OpenStack performance testing at scale',
      long_description=read('README.md'),
      url='https://github.com/target/cloudpunch',
      author='Jacob Lube',
      author_email='jacob.lube@target.com',
      keywords='OpenStack cloudpunch performance',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: OpenStack',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: MIT License',
          'Operating Systems :: Linux',
          'Operating Systems :: MacOS',
          'Programming Language :: Python',
          'Programming Language :: Python 2',
          'Programming Language :: Python 2.7'
      ],
      packages=[
          'cloudpunch',
          'cp_master',
          'cp_slave'
      ],
      install_requires=[
          'flask==0.11.1',
          'redis==2.10.5',
          'requests==2.11.1',
          'tabulate==0.7.5',
          'futures==3.0.5',
          'pyyaml==3.12',
          'python-keystoneclient==3.6.0',
          'python-novaclient==6.0.0',
          'python-neutronclient==6.0.0',
          'python-cinderclient==1.9.0',
          'datadog==0.14.0'
      ],
      entry_points={
          'console_scripts': [
              'cloudpunch = cloudpunch.cloudpunch:main',
              'cloudpunch-post = cloudpunch.post:main',
              'cloudpunch-cleanup = cloudpunch.cleanup:main',
              'cloudpunch-master = cp_master.cp_master:main',
              'cloudpunch-slave = cp_slave.cp_slave:main'
          ]
      })
