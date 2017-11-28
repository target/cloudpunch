import logging
import time

from kafka import KafkaProducer

import cloudpunch.utils.config as cpc
import cloudpunch.utils.sysinfo as sysinfo


class Metrics(object):

    def __init__(self, config):
        self.config = config
        logging.debug('Connecting to Kafka server(s): %s', ', '.join(self.config['brokers']))
        self.producer = KafkaProducer(bootstrap_servers=self.config['brokers'])

    def send_metric(self, name, value, timestamp=None, extra_tags={}):
        tags = {
            'app': 'cloudpunch',
            'testnumber': sysinfo.testnum(),
            'hostname': sysinfo.hostname(),
            'role': sysinfo.role()
        }
        fields = {
            'value': value
        }
        tags = cpc.merge_configs(tags, extra_tags)
        tags = cpc.merge_configs(tags, self.config['tags'])
        self.send(name, tags, fields, timestamp)

    def send(self, name, tags, fields, timestamp=None):
        # Use current time if no timestamp is provided
        if not timestamp:
            timestamp = int(time.time())
        # Convert timestamp to microseconds from seconds (influx requires)
        timestamp_final = timestamp * (10**9)

        # Process tags
        processed_tags = []
        for tagname, tagvalue in tags.items():
            # Tags need spaces escaped
            processed_tags.append('%s=%s' % (tagname, str(tagvalue).replace(' ', '\ ')))

        # Process fields
        processed_fields = []
        for fieldname, fieldvalue in fields.items():
            # Integers must have an i (123i)
            if isinstance(fieldvalue, int):
                field_value = '%si' % fieldvalue
            # Floats need nothing extra, just converted to str
            elif isinstance(fieldvalue, float):
                field_value = str(fieldvalue)
            # Strings need to have double quotes
            else:
                field_value = '"%s"' % fieldvalue
            processed_fields.append('%s=%s' % (fieldname, field_value))

        # Sort tags for better performance
        processed_tags.sort()

        # Build the final converted message
        tags_final = ','.join(processed_tags)
        fields_final = ','.join(processed_fields)
        converted = '%s,%s %s %s' % (name, tags_final, fields_final, timestamp_final)
        logging.debug('Converted message to Influx DB: %s', converted)

        # Send the message to Kafka
        logging.debug('Sending converted message to Kafka topic %s', self.config['topic'])
        self.producer.send(self.config['topic'], value=converted.encode())
        logging.debug('Completed send to Kafka')
