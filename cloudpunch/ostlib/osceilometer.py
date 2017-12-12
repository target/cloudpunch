import logging

import ceilometerclient.client as cclient

import exceptions


class BaseCeilometer(object):

    def __init__(self, session, region_name=None, api_version=2):
        # Create the ceilometer object which handles interaction with the API
        self.ceilometer = cclient.Client(str(api_version),
                                         session=session,
                                         region_name=region_name)
        self.session = session
        self.api_version = api_version


class Alarm(BaseCeilometer):

    def delete(self, alarm_id=None):
        alarm = self.get(alarm_id)
        try:
            self.ceilometer.alarms.delete(alarm.id)
            logging.debug('Deleted alarm %s with ID %s', alarm.name, alarm.id)
            return True
        except Exception:
            logging.error('Failed to delete alarm %s with ID %s', alarm.name, alarm.id)
            return False

    def list(self, project_id=None, all_projects=False):
        alarm_info = []
        alarms = self.ceilometer.alarms.list()
        for alarm in alarms:
            if not all_projects and project_id and alarm.project_id != project_id:
                continue
            if not all_projects and not project_id and alarm.project_id != self.session.get_project_id():
                continue
            alarm_info.append({
                'id': alarm.id,
                'name': alarm.name
            })
        return alarm_info

    def load(self, alarm_id):
        self.alarm = self.ceilometer.alarms.get(alarm_id)

    def get(self, alarm_id=None, use_cached=False):
        if alarm_id:
            return self.ceilometer.alarms.get(alarm_id)
        try:
            if use_cached:
                return self.alarm
            return self.ceilometer.alarms.get(self.get_id())
        except AttributeError:
            raise exceptions.OSTLibError('No alarm supplied and no cached alarm')

    def get_name(self, alarm_id=None, use_cached=False):
        alarm = self.get(alarm_id, use_cached)
        return alarm.name

    def get_id(self, alarm_name=None, project_id=None, all_projects=False):
        if alarm_name:
            alarms = self.list(project_id, all_projects)
            for alarm in alarms:
                if alarm['name'] == alarm_name:
                    return alarm['id']
            raise exceptions.OSTLibError('Alarm %s was not found' % alarm_name)
        alarm = self.get(use_cached=True)
        return alarm.id
