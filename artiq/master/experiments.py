import asyncio
import os
import tempfile
import shutil
import logging
from functools import partial

from artiq.protocols.sync_struct import Notifier
from artiq.master.worker import Worker
from artiq.tools import exc_to_warning


logger = logging.getLogger(__name__)


async def _get_repository_entries(entry_dict,
                                  root, filename, get_device_db, log):
    worker = Worker({
        "get_device_db": get_device_db,
        "log": partial(log, "scan")
    })
    try:
        description = await worker.examine(os.path.join(root, filename))
    finally:
        await worker.close()
    for class_name, class_desc in description.items():
        name = class_desc["name"]
        arginfo = class_desc["arginfo"]
        if "/" in name:
            logger.warning("Character '/' is not allowed in experiment "
                           "name (%s)", name)
            name = name.replace("/", "_")
        if name in entry_dict:
            logger.warning("Duplicate experiment name: '%s'", name)
            basename = name
            i = 1
            while name in entry_dict:
                name = basename + str(i)
                i += 1
        entry = {
            "file": filename,
            "class_name": class_name,
            "arginfo": arginfo
        }
        entry_dict[name] = entry


async def _scan_experiments(root, get_device_db, log, subdir=""):
    entry_dict = dict()
    for de in os.scandir(os.path.join(root, subdir)):
        if de.name.startswith("."):
            continue
        if de.is_file() and de.name.endswith(".py"):
            filename = os.path.join(subdir, de.name)
            try:
                await _get_repository_entries(
                    entry_dict, root, filename, get_device_db, log)
            except:
                logger.warning("Skipping file '%s'", filename, exc_info=True)
        if de.is_dir():
            subentries = await _scan_experiments(
                root, get_device_db, log,
                os.path.join(subdir, de.name))
            entries = {de.name + "/" + k: v for k, v in subentries.items()}
            entry_dict.update(entries)
    return entry_dict


def _sync_explist(target, source):
    for k in list(target.read.keys()):
        if k not in source:
            del target[k]
    for k in source.keys():
        if k not in target.read or target.read[k] != source[k]:
            target[k] = source[k]


class ExperimentDB:
    def __init__(self, repo_backend, get_device_db_fn, log_fn):
        self.repo_backend = repo_backend
        self.get_device_db_fn = get_device_db_fn
        self.log_fn = log_fn

        self.cur_rev = self.repo_backend.get_head_rev()
        self.repo_backend.request_rev(self.cur_rev)
        self.explist = Notifier(dict())

        self._scanning = False

    def close(self):
        # The object cannot be used anymore after calling this method.
        self.repo_backend.release_rev(self.cur_rev)

    async def scan_repository(self, new_cur_rev=None):
        if self._scanning:
            return
        self._scanning = True
        try:
            if new_cur_rev is None:
                new_cur_rev = self.repo_backend.get_head_rev()
            wd, _ = self.repo_backend.request_rev(new_cur_rev)
            self.repo_backend.release_rev(self.cur_rev)
            self.cur_rev = new_cur_rev
            new_explist = await _scan_experiments(wd, self.get_device_db_fn,
                                                  self.log_fn)

            _sync_explist(self.explist, new_explist)
        finally:
            self._scanning = False

    def scan_repository_async(self, new_cur_rev=None):
        asyncio.ensure_future(exc_to_warning(self.scan_repository(new_cur_rev)))

    async def examine(self, filename, use_repository=True):
        if use_repository:
            revision = self.cur_rev
            wd, _ = self.repo_backend.request_rev(revision)
            filename = os.path.join(wd, filename)
        worker = Worker({
            "get_device_db": self.get_device_db_fn,
            "log": partial(self.log_fn, "examine")
        })
        try:
            description = await worker.examine(filename)
        finally:
            await worker.close()
        if use_repository:
            self.repo_backend.release_rev(revision)
        return description


class FilesystemBackend:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def get_head_rev(self):
        return "N/A"

    def request_rev(self, rev):
        return self.root, None

    def release_rev(self, rev):
        pass


class _GitCheckout:
    def __init__(self, git, rev):
        self.path = tempfile.mkdtemp()
        commit = git.get(rev)
        git.checkout_tree(commit, directory=self.path)
        self.message = commit.message.strip()
        self.ref_count = 1
        logger.info("checked out revision %s into %s", rev, self.path)

    def dispose(self):
        logger.info("disposing of checkout in folder %s", self.path)
        shutil.rmtree(self.path)


class GitBackend:
    def __init__(self, root):
        # lazy import - make dependency optional
        import pygit2

        self.git = pygit2.Repository(root)
        self.checkouts = dict()

    def get_head_rev(self):
        return str(self.git.head.target)

    def request_rev(self, rev):
        if rev in self.checkouts:
            co = self.checkouts[rev]
            co.ref_count += 1
        else:
            co = _GitCheckout(self.git, rev)
            self.checkouts[rev] = co
        return co.path, co.message

    def release_rev(self, rev):
        co = self.checkouts[rev]
        co.ref_count -= 1
        if not co.ref_count:
            co.dispose()
            del self.checkouts[rev]
