from schedules_tools import storage
import datetime
import os
import shutil
import tempfile


class StorageHandler_local(storage.StorageBase):
    def get_local_handle(self, revision=None, datetime=None):
        self.tmp_root = self._copy_subtree_to_tmp()
        handle_filename = os.path.basename(self.handle)

        return os.path.join(self.tmp_root, handle_filename)

    def clean_local_handle(self):
        shutil.remove_tree(self.tmp_root)

    def get_changelog(self, path=None):
        return []

    def get_mtime(self, path=None):
        mtime_timestamp = os.path.getmtime(self.handle)

        return datetime.datetime.fromtimestamp(mtime_timestamp)

    def _copy_subtree_to_tmp(self):
        """
        Create an independent copy of product (from main-cvs-checkout),
        located in /tmp and

        Returns:
            Path to process_path copied directory  in /tmp
        """
        dst_tmp_dir = tempfile.mkdtemp(prefix='sch_')
        shutil.copy2(self.handle, dst_tmp_dir)

        return dst_tmp_dir