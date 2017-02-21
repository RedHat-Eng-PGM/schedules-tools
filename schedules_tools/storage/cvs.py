from schedules_tools.storage import ScheduleStorageBase
import os
import sys
import re
import subprocess
import datetime
import tempfile
import logging

logger = logging.getLogger(__name__)


class ScheduleStorage_cvs(ScheduleStorageBase):
    target_dir = None
    cloned = False
    repo_root = None
    repo_name = None

    def _cvs_command(self, cmd):
        # -q, make cvs more quiet
        # -z9, maximum compression
        # -d, set CVSROOT
        cmd_str = 'cvs -q -z9 -d {} {}'.format(self.repo_root, cmd)
        p = subprocess.Popen(cmd_str.split(), stdout=sys.stdout,
                             cwd=self.target_dir)
        return p

    def __init__(self, opt_args=dict()):
        self.repo_name = opt_args.pop('cvs_repo_name')
        self.repo_root = opt_args.pop('cvs_root')
        self.opt_args = opt_args

    def _clone(self, target_dir=None):
        if self.cloned:
            logger.debug('Storage has been already cloned. Skipping.')
            return
        if not target_dir:
            target_dir = '/tmp'
        self.target_dir = target_dir
        tempfile.mkdtemp()
        os.makedirs(self.target_dir)

        cmd = 'co {}'.format(self.repo_name)
        p = self._cvs_command(cmd)
        p.communicate()

        assert p.returncode == 0
        self.cloned = True

        return self.target_dir

    def _checkout(self, revision=None, filename=None):
        if not filename:
            filename = ''
        cmd = 'update -r{revision} {filename}'.format(revision=revision,
                                                      filename=filename)
        p = self._cvs_command(cmd)
        p.communicate()
        assert p.returncode == 0

    def pull(self, rev=None, datetime=None, target_dir=None):
        """ Pulls from storage

        Args:
            rev: if None - pull current
            date:
            target_dir: if None, pull to tmp dir

        Returns:
            Pulled file/directory
        """
        self._clone(target_dir)
        # TODO(mpavlase): pass desired file/dir to checkout
        self._checkout(revision=rev)
        # TODO - return resulting filename

    def parse_changelog(self, filename):
        changelog = []
        cmd = 'cvs log {}'.format(filename)
        p = subprocess.Popen(cmd.split(), env=self.envvars, cwd=self.target_dir,
                             stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()

        STATE_HEAD = 'head'
        STATE_REVISION = 'revision'
        STATE_DATE_AUTHOR = 'dateauthor'
        STATE_COMMENT = 'comment'

        state = STATE_HEAD

        revision = None
        author = None
        date = None
        comment = []
        re_date_author = re.compile('date:\s*([^;]+);\s+author:\s*([^;]+);')
        re_head = re.compile('head:\s+(.+)')
        re_revision = re.compile('revision\s+(.+)')
        re_branches = re.compile('branches:\s+(.+);')
        log_separator = '----------------------------'

        for line in stdout.splitlines():
            if state == STATE_HEAD:
                matches = re_head.findall(line)
                if not matches:
                    continue
                self.latest_change = matches[0]

                state = STATE_REVISION
                continue
            elif state == STATE_REVISION:
                # new record, clean all previous values
                matches = re_revision.findall(line)
                if not matches:
                    continue
                revision = matches[0]
                author = None
                date = None
                comment = []

                state = STATE_DATE_AUTHOR
                continue
            elif state == STATE_DATE_AUTHOR:
                matches = re_date_author.findall(line)
                date = datetime.datetime.strptime(matches[0][0],
                                                  '%Y/%m/%d %H:%M:%S')
                author = matches[0][1]
                comment = []

                state = STATE_COMMENT
                continue
            elif state == STATE_COMMENT:
                br = re_branches.match(line)
                if not comment and br:
                    continue
                if line == log_separator:
                    # store whole log
                    comment = '\n'.join(comment)
                    record = {
                        'revision': revision,
                        'author': author,
                        'date': date,
                        'message': comment
                    }
                    changelog.append(record)
                    state = STATE_REVISION
                    continue
                comment.append(line)
                continue

        # sort records according to date
        return sorted(changelog, key=lambda x: x.date)
