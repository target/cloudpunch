import logging
import time

from heatclient import client as hclient

import exceptions


class BaseHeat(object):

    def __init__(self, session, region_name=None, api_version=1):
        # Create the heat object which handles interaction with the API
        self.heat = hclient.Client(str(api_version),
                                   session=session,
                                   region_name=region_name)
        self.api_version = api_version


class Stack(BaseHeat):

    def create(self, name, template_dict, parameters_dict=None,
               timeout_mins=60, disable_rollback=False, wait_for_complete=True):
        heat_body = {
            'name': name,
            'template': template_dict,
            'timeout_mins': timeout_mins,
            'disable_rollback': disable_rollback
        }
        if parameters_dict:
            heat_body['parameters'] = parameters_dict
        self.stack = self.heat.stacks.create(heat_body)
        logging.debug('Created stack %s with ID %s', name, self.get_id())
        if wait_for_complete:
            logging.debug('Waiting for stack to complete')
            for _ in range(timeout_mins * 60):
                stack_status = self.get(self.get_id()).stack_status
                if stack_status == 'CREATE_COMPLETE':
                    logging.debug('Stack %s with ID %s is now complete', name, self.get_id())
                    break
                elif stack_status != 'CREATE_IN_PROGRESS':
                    raise exceptions.OSTLibError('Stack %s with ID %s failed to create', name, self.get_id())
                time.sleep(1)

    def delete(self, stack_id=None, timeout=60):
        stack = self.get(stack_id)
        self.heat.stacks.delete(stack.id)
        logging.debug('Starting delete process on stack %s with ID %s', stack.stack_name, stack.id)
        for _ in range(timeout):
            stack_status = self.get(stack.id).stack_status
            if stack_status == 'DELETE_COMPLETE':
                logging.debug('Successfully deleted stack %s with ID %s', stack.stack_name, stack.id)
                return True
            elif stack_status != 'DELETE_IN_PROGRESS':
                logging.debug('Failed to delete stack %s with ID %s', stack.stack_name, stack.id)
                return False
            time.sleep(1)
        return False

    def load(self, stack_id):
        self.stack = self.heat.stacks.get(stack_id)

    def list(self):
        stack_info = []
        stacks = list(self.heat.stacks.list())
        for stack in stacks:
            stack_info.append({
                'id': stack.id,
                'name': stack.stack_name
            })
        return stack_info

    def get(self, stack_id=None, use_cached=False):
        if stack_id:
            return self.heat.stacks.get(stack_id)
        try:
            if use_cached:
                return self.stack
            return self.heat.stacks.get(self.get_id())
        except AttributeError:
            raise exceptions.OSTLibError('No heat stack supplied and no cached heat stack')

    def get_name(self, stack_id=None, use_cached=True):
        stack = self.get(stack_id, use_cached)
        return stack.stack_name

    def get_id(self, stack_name=None):
        if stack_name:
            stacks = self.list()
            for stack in stacks:
                if stack['name'] == stack_name:
                    return stack['id']
            raise exceptions.OSTLibError('Heat stack %s was not found' % stack_name)
        stack = self.get(use_cached=True)
        return stack.id
