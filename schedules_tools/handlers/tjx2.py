from . import ScheduleHandlerBase, TJXChangelog
import datetime
import logging
from schedules_tools import models
import os

from lxml import etree
logger = logging.getLogger('pp.core')


class ScheduleHandler_tjx2(ScheduleHandlerBase, TJXChangelog):
    provide_export = False
    task_index = 1

    @staticmethod
    def is_valid_source(handle):
        file_ext = os.path.splitext(handle)[1]

        if file_ext == '.tjx':
            tree = etree.parse(handle)
            if tree.xpath('/taskjuggler/project[@name]'):
                return True
        return False

    @staticmethod
    def _load_tjx_date(eTask, datetype, what=''):
        '''Returns datetime with datetype = plan|actual what = start|end'''
        xpath = './taskScenario[@scenarioId=\'{}\']/{}'.format(datetype, what)
        tag = eTask.xpath(xpath)
        if tag:
            return datetime.datetime.fromtimestamp(float(tag[0].text))
        else:
            return None

    def _parse_task_element(self, task, eTask):
        task.index = self.task_index
        self.task_index += 1
        task.tjx_id = eTask.get('id')
        task.name = eTask.get('name')
        # TBD - notes
        task.priority = eTask.get('priority')
        task.milestone = eTask.get('milestone') == '1'
        # TBD - complete

        task.dStart = self._load_tjx_date(eTask, 'plan', 'start')
        task.dAcStart = self._load_tjx_date(eTask, 'actual', 'start')
        if task.milestone:
            task.dFinish = task.dStart
            task.dAcFinish = task.dAcStart
        else:
            task.dFinish = self._load_tjx_date(eTask, 'plan', 'end')
            task.dAcFinish = self._load_tjx_date(eTask, 'actual', 'end')

        # TODO: ask, if it's still needed
        # copy & pasted from .tjx
        #acStart = self._load_tjx_date(eTask, 'actual', 'start')
        #if acStart:
        #    task.dAcStart = acStart
        #acFinish = self._load_tjx_date(eTask, 'actual', 'end')
        #if acFinish:
        #    task.dAcFinish = acFinish
        for eFlag in eTask.xpath('./flag'):
            task.flags.append(eFlag.text)

        link_el = eTask.xpath('customAttribute[@id="PTask"]/referenceAttribute')
        if link_el:
            task.link = link_el[0].get('url')

        # add flags from task to global used tags
        task._schedule.used_flags |= set(task.flags)

        min_date = task.dStart
        max_date = task.dAcFinish

        task.check_for_phase()

        for eSubTask in eTask.xpath('./task'):
            item_task = models.Task(self.schedule, task.level + 1)
            t_min_date, t_max_date = self._parse_task_element(item_task,
                                                              eSubTask)
            min_date = min(min_date, t_min_date)
            max_date = max(max_date, t_max_date)

            task.tasks.append(item_task)
        return min_date, max_date

    def import_schedule(self, handle):
        self.schedule = models.Schedule()
        tree = etree.parse(handle)
        el_proj = tree.xpath('/taskjuggler/project')[0]
        self.schedule.name = '%s %s' % (el_proj.get('name'),
                                        el_proj.get('version'))
        self.schedule.proj_id = el_proj.get('id')

        # import changelog
        self.parse_changelog(el_proj)

        min_date = datetime.datetime.max
        max_date = datetime.datetime.min

        for task in tree.xpath('/taskjuggler/taskList/task'):
            item_task = models.Task(self.schedule)
            self._parse_task_element(item_task, task)
            min_date = min(min_date, item_task.dStart)
            max_date = max(max_date, item_task.dFinish)
            self.schedule.tasks.append(item_task)

        if self.schedule.tasks:
            self.schedule.dStart = min_date
            self.schedule.dFinish = max_date
            self.schedule.check_top_task()
            self.schedule.name = self.schedule.tasks[0].name
        else:
            # try to load dates from project level
            tag = el_proj.xpath('start')[0].text
            start = datetime.datetime.fromtimestamp(float(tag))
            if start:
                self.schedule.dStart = start

            tag = el_proj.xpath('end')[0].text
            end = datetime.datetime.fromtimestamp(float(tag))
            if end:
                self.schedule.dFinish = end

        return self.schedule