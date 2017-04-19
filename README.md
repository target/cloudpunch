# CloudPunch

Framework for performance testing an OpenStack environment at scale

[CloudPunch Documentation](./docs/README.md)

## Features

- **Written 100% in Python** - CloudPunch is written in the Python language including the sections that stage OpenStack and the tests that run. This was chosen to avoid reliance on other tools.

- **Create custom tests** - Because tests are written in Python, custom written tests can be ran by simply dropping a file in a folder. These tests are not limited; a test can do anything Python can do.

- **Fully scalable** - A test can include one instance or hundreds. A couple lines of configuration can drastically change the stress put on OpenStack hardware.

- **Test across OpenStack environments** - Have multiple OpenStack environments or regions? Run tests across them to see performance metrics when they interact.

- **Run tests in an order or all at once** - See single metric results such as network throughput or see how a high network throughput can affect network latency.

- **JSON and YAML support** - Use a mix of JSON or YAML for both configuration and results

## License

MIT License

Copyright (c) 2017 Target Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

CloudPunch uses other open source projects:

- Redis - [BSD License](http://redis.io/topics/license)
- FIO - [GPL v2](https://raw.githubusercontent.com/axboe/fio/master/MORAL-LICENSE)
- iPerf3 - [BSD License](https://raw.githubusercontent.com/esnet/iperf/master/LICENSE)
