# Create the CloudPunch egg
FROM python:2
RUN mkdir -p /opt/cloudpunch
COPY . /opt/cloudpunch
WORKDIR /opt/cloudpunch
RUN python setup.py bdist_egg
COPY dist/*.egg .

# Install the CloudPunch egg
FROM python:2
WORKDIR /root/
COPY --from=0 /opt/cloudpunch/dist/*.egg .
RUN easy_install $(ls *.egg)
