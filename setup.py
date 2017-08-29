import sys
import os

from setuptools import setup

if not sys.version_info[0] >= 2:
    sys.exit('Requires Python 2')


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


def read_reqs(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read().strip().split('\n')


setup(name='cloudpunch',
      version=read('cloudpunch/version'),
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
          'cloudpunch.master',
          'cloudpunch.ostlib',
          'cloudpunch.slave',
          'cloudpunch.utils'
      ],
      include_package_data=True,
      install_requires=read_reqs('requirements.txt'),
      entry_points={
          'console_scripts': [
              'cloudpunch = cloudpunch.app:main',
          ]
      })
