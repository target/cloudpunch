# Create the CloudPunch egg
FROM python:2 AS build
RUN mkdir -p /opt/cloudpunch
COPY . /opt/cloudpunch
WORKDIR /opt/cloudpunch
RUN python setup.py bdist_egg

# Install the CloudPunch egg
FROM python:2
WORKDIR /root/
COPY --from=build /opt/cloudpunch/dist/*.egg ./
RUN easy_install $(ls *.egg)
CMD ["/bin/bash"]
