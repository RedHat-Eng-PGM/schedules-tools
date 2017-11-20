import datetime
import os
import json
import logging

from schedules_tools.schedule_handlers import ScheduleHandlerBase
from schedules_tools.models import Schedule, Task

logger = logging.getLogger(__name__)


class ScheduleHandler_json(ScheduleHandlerBase):
    provide_export = True

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle
        file_ext = os.path.splitext(handle)[1]

        if file_ext != '.json':
            return False
        try:
            with open(handle) as fd:
                json.load(fd)
        except ValueError:
            return False

        return True

    @staticmethod
    def _parse_timestamp(timestamp):
        number = int(timestamp)
        return datetime.datetime.fromtimestamp(number)

    def import_schedule(self):
        with open(self.handle) as fd:
            jsonobj = json.load(fd)

        schedule = Schedule()
        schedule.dStart = self._parse_timestamp(jsonobj['start'])
        schedule.dFinish = self._parse_timestamp(jsonobj['end'])
        schedule.slug = jsonobj['slug']
        schedule.name = jsonobj['name']

        # TODO!
        # verity if the changelog is in correct format
        schedule.changelog = jsonobj['changelog']

        # We don't parse phases here, because we are collecting them
        # during parsing tasks itself

        for subtaskobj in jsonobj['tasks']:
            task = self.import_task_from_json(schedule, subtaskobj, None)
            schedule.tasks.append(task)
        return schedule

    def import_task_from_json(self, schedule, jsonobj, parenttask):
        task = Task(schedule)

        task.index = jsonobj['index']
        task.level = jsonobj['_level']
        task.name = jsonobj['name']
        task.slug = jsonobj['slug']

        task.priority = jsonobj['priority']
        task.p_complete = jsonobj['complete']
        task.milestone = False
        if jsonobj['type'] == 'Milestone':
            task.milestone = True
        task.flags = jsonobj['flags']

        if 'link' in jsonobj:
            task.link = jsonobj['link']

        if 'note' in jsonobj:
            task.note = jsonobj['note']

        task.dStart = self._parse_timestamp(jsonobj['planStart'])
        task.dFinish = self._parse_timestamp(jsonobj['planEnd'])

        task.dAcStart = self._parse_timestamp(jsonobj['actualStart'])
        task.dAcFinish = self._parse_timestamp(jsonobj['actualEnd'])

        schedule.used_flags |= set(task.flags)

        if 'tasks' in jsonobj:
            for subtaskobj in jsonobj['tasks']:
                subtask = self.import_task_from_json(schedule, subtaskobj, task)
                task.tasks.append(subtask)

        task.check_for_phase()

        return task

    def export_schedule(self, out_file, flat=False):
        json_schedule = self.export_schedule_as_dict(flat)
        content = json.dumps(json_schedule,
                             sort_keys=True,
                             indent=4,
                             separators=(',', ': '))

        self._write_to_file(content, out_file)

        return content

    def export_schedule_as_dict(self, flat=False):
        schedule_dict = dict()
        schedule_dict['slug'] = self.schedule.slug
        schedule_dict['name'] = self.schedule.name
        schedule_dict['start'] = self.schedule.dStart.strftime('%s')
        schedule_dict['end'] = self.schedule.dFinish.strftime('%s')

        now = datetime.datetime.now()
        schedule_dict['now'] = now.strftime('%s')

        schedule_dict['changelog'] = self.schedule.changelog
        for log in self.schedule.changelog.itervalues():
            log['date'] = datetime.datetime.strftime(log['date'], '%Y-%m-%d')

        schedule_dict['tasks'] = []
        self.schedule.task_id_reg = set()

        if flat:
            add_task_func = schedule_dict['tasks'].extend
        else:
            add_task_func = schedule_dict['tasks'].append

        for task in self.schedule.tasks:
            add_task_func(self.task_export_json_obj(task, flat=flat))

        schedule_dict['phases'] = []
        for phase in self.schedule.phases:
            schedule_dict['phases'].append(self.export_phase_as_dict(phase))

        return schedule_dict

    def export_task_as_dict(self, task, parent_slug='', flat=False):
        task_export = {}

        task_export['slug'] = task.slug
        task_export['index'] = task.index
        task_export['_level'] = task.level
        task_export['name'] = task.name
        task_export['priority'] = task.priority
        task_export['complete'] = task.p_complete
        task_export['type'] = task.get_type()
        task_export['flags'] = task.flags

        if task.note:
            task_export['note'] = task.note
        if task.link:
            task_export['link'] = task.link

        task_export['parentTask'] = parent_slug

        task_export['planStart'] = task.dStart.strftime('%s')
        task_export['planEnd'] = task.dFinish.strftime('%s')
        task_export['actualStart'] = task.dAcStart.strftime('%s')
        task_export['actualEnd'] = task.dAcFinish.strftime('%s')

        task_list = [task_export]

        if task.tasks:  # task has subtasks
            # prepare tasklist
            if flat:
                add_func = task_list.extend
            else:
                task_export['tasks'] = []
                add_func = task_export['tasks'].append

            for subtask in task.tasks:
                add_func(self.export_task_as_dictj(
                    subtask, task.slug, flat))

        if flat:
            return task_list
        else:
            return task_export

    def export_phase_as_dict(self, phase):
        phase_export = dict()
        phase_export['name'] = phase.name
        phase_export['complete'] = phase.p_complete
        phase_export['planStart'] = phase.dStart.strftime('%s')
        phase_export['planEnd'] = phase.dFinish.strftime('%s')
        phase_export['actualStart'] = phase.dAcStart.strftime('%s')
        phase_export['actualEnd'] = phase.dAcFinish.strftime('%s')

        return phase_export
