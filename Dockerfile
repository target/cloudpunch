# Create the CloudPunch egg
FROM python:2
RUN mkdir -p /opt/cloudpunch
COPY . /opt/cloudpunch
WORKDIR /opt/cloudpunch
RUN python setup.py bdist_egg
COPY dist/*.egg .

# Install required packages and the CloudPunch egg
FROM python:2
RUN apt-get update && \
    apt-get install -y redis-server && \
    apt-get clean
WORKDIR /root/
COPY --from=0 /opt/cloudpunch/dist/*.egg .
RUN easy_install $(ls *.egg)
