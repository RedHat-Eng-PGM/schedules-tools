from schedules_tools.schedule_handlers import ScheduleHandlerBase
from schedules_tools import models
from smartsheet import Smartsheet
import logging
import datetime
import re


COLUMN_TASK_NAME = 'name'
COLUMN_DURATION = 'duration'
COLUMN_START = 'start'
COLUMN_ACSTART = 'acstart'
COLUMN_FINISH = 'finish'
COLUMN_ACFINISH = 'acfinish'
COLUMN_P_COMPLETE = 'complete'
COLUMN_NOTE = 'note'
COLUMN_FLAGS = 'flags'
COLUMN_LINK = 'link'
COLUMN_PRIORITY = 'priority'

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
smartsheet_logger = logging.getLogger('smartsheet.smartsheet')
smartsheet_logger.setLevel(logging.INFO)


class ScheduleHandler_smartsheet(ScheduleHandlerBase):
    provide_export = False
    date_format = '%Y-%m-%dT%H:%M:%S'  # 2017-01-20T08:00:00
    _client_instance = None
    _sheet_instance = None
    _re_number = re.compile('[0-9]+')
    columns_mapping_name = {
        'Task Name': COLUMN_TASK_NAME,
        'Duration': COLUMN_DURATION,
        'Start': COLUMN_START,
        'Finish': COLUMN_FINISH,
        '% Complete': COLUMN_P_COMPLETE,
        'Comments': COLUMN_NOTE,
        'Flags': COLUMN_FLAGS,
        'Link': COLUMN_LINK,
        'Actual Start': COLUMN_ACSTART,
        'Actual Finish': COLUMN_ACFINISH,
        'Priority': COLUMN_PRIORITY,
    }

    columns_mapping_id = {}

    def __init__(self, *args, **kwargs):
        super(ScheduleHandler_smartsheet, self).__init__(*args, **kwargs)

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle
        try:
            int(handle)
            #cls.client.get_sheet(handle)
        except ValueError:
            return False

        return True

    @property
    def client(self):
        if not self._client_instance:
            self._client_instance = Smartsheet(self.options['smartsheet_token'])
            self._client_instance.errors_as_exceptions(True)
        return self._client_instance

    @property
    def sheet(self):
        if not self._sheet_instance:
            self._sheet_instance = self.client.Sheets.get_sheet(self.handle)
        return self._sheet_instance

    def get_handle_mtime(self):
        return self.sheet.modified_at

    def import_schedule(self):
        self.schedule = models.Schedule()
        self.schedule.name = self.sheet.name
        self.schedule.slug = self.schedule.unique_id_re.sub('_', self.schedule.name)
        self.schedule.mtime = self.get_handle_mtime()
        parents_stack = []

        # populate columns dict/map
        for column in self.sheet.columns:
            index = self.columns_mapping_name.get(column.title, None)
            if index is None:
                logger.debug('Unknown column %s, skipping.' % column.title)
                continue
            self.columns_mapping_id[column.id] = index

        for row in self.sheet.rows:
            self._load_task(row, parents_stack)

        self.schedule.check_top_task()
        self.schedule.dStart = self.schedule.tasks[0].dStart
        self.schedule.dFinish = self.schedule.tasks[0].dFinish
        self.schedule.generate_slugs()
        return self.schedule

    def _parse_date(self, string):
        date = datetime.datetime.strptime(string, self.date_format)
        # We don't require so precise timestamp, so ignore seconds
        date = date.replace(second=0)
        return date

    def _load_task(self, row, parents_stack):
        task = models.Task(self.schedule)
        cells = self._load_task_cells(row)

        task.index = row.row_number
        # task.slug is generated at the end of importing whole schedule
        task.name = cells[COLUMN_TASK_NAME]

        # skip empty rows
        if not task.name:
            return

        task.note = cells[COLUMN_NOTE]
        if COLUMN_PRIORITY in cells:
            task.priority = cells[COLUMN_PRIORITY]

        task.dStart = self._parse_date(cells[COLUMN_START])
        task.dFinish = self._parse_date(cells[COLUMN_FINISH])
        if COLUMN_ACSTART in cells:
            task.dAcStart = cells[COLUMN_ACSTART]
        else:
            task.dAcStart = task.dStart

        if COLUMN_ACFINISH in cells:
            task.dAcFinish = cells[COLUMN_ACFINISH]
        else:
            task.dAcFinish = task.dFinish

        if COLUMN_DURATION in cells:
            # duration cell contains values like '14d', '~0'
            match = re.findall(self._re_number, cells[COLUMN_DURATION])
            if match:
                task.milestone = int(match[0]) == 0
        task.p_complete = round(cells[COLUMN_P_COMPLETE] * 100, 1)
        if COLUMN_FLAGS in cells and cells[COLUMN_FLAGS]:
            # try first to parse workaround format 'Flags: qe, dev'
            task.parse_extended_attr(cells[COLUMN_FLAGS])

            # then try to consider the value as it is 'qe, dev'
            if not task.flags:
                task.parse_extended_attr(cells[COLUMN_FLAGS],
                                         force_key=models.ATTR_PREFIX_FLAG)

        if COLUMN_LINK in cells and cells[COLUMN_LINK]:
            # try first to parse workaround format 'Link: http://some.url'
            task.parse_extended_attr(cells[COLUMN_LINK])
            # then try to consider the value as it is 'http://some.url'
            if not task.link:
                task.parse_extended_attr(cells[COLUMN_LINK],
                                         force_key=models.ATTR_PREFIX_LINK)

        curr_stack_item = {
            'rowid': row.id,
            'task': task
        }
        if not parents_stack:
            # Current task is the topmost (root)
            self.schedule.tasks = [task]
            parents_stack.insert(0, curr_stack_item)
        elif row.parent_id == parents_stack[0]['rowid']:
            # Current task is direct descendant of latest task
            parents_stack[0]['task'].tasks.append(task)
            parents_stack.insert(0, curr_stack_item)
        elif row.parent_id != parents_stack[0]['rowid']:
            # We are currently in the same, or upper, level of tree
            while row.parent_id != parents_stack[0]['rowid']:
                parents_stack.pop(0)
            parents_stack[0]['task'].tasks.append(task)
            parents_stack.insert(0, curr_stack_item)

        task.check_for_phase()
        task.level = len(parents_stack)

    def _load_task_cells(self, row):
        mapped_cells = {}

        for cell in row.cells:
            cell_name = self.columns_mapping_id.get(cell.column_id, None)
            if not cell_name:
                continue

            mapped_cells[cell_name] = cell.value

        return mapped_cells