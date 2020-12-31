import asyncio
import os
import tempfile
import shutil
import time
import logging

from sipyco.sync_struct import Notifier, update_from_dict

from artiq.master.worker import (Worker, WorkerInternalException,
                                 log_worker_exception)
from artiq.tools import get_windows_drives, exc_to_warning


logger = logging.getLogger(__name__)


class _RepoScanner:
    def __init__(self, worker_handlers):
        self.worker_handlers = worker_handlers
        self.worker = None

    async def process_file(self, entry_dict, root, filename):
        logger.debug("processing file %s %s", root, filename)
        try:
            description = await self.worker.examine(
                "scan", os.path.join(root, filename))
        except:
            log_worker_exception()
            raise
        for class_name, class_desc in description.items():
            name = class_desc["name"]
            arginfo = class_desc["arginfo"]
            if "/" in name:
                logger.warning("Character '/' is not allowed in experiment "
                               "name (%s)", name)
                name = name.replace("/", "_")
            if name in entry_dict:
                basename = name
                i = 1
                while name in entry_dict:
                    name = basename + str(i)
                    i += 1
                logger.warning("Duplicate experiment name: '%s'\n"
                               "Renaming class '%s' in '%s' to '%s'",
                               basename, class_name, filename, name)
            entry = {
                "file": filename,
                "class_name": class_name,
                "arginfo": arginfo,
                "scheduler_defaults": class_desc["scheduler_defaults"]
            }
            entry_dict[name] = entry

    async def _scan(self, root, subdir=""):
        entry_dict = dict()
        for de in os.scandir(os.path.join(root, subdir)):
            if de.name.startswith("."):
                continue
            if de.is_file() and de.name.endswith(".py"):
                filename = os.path.join(subdir, de.name)
                try:
                    await self.process_file(entry_dict, root, filename)
                except Exception as exc:
                    logger.warning("Skipping file '%s'", filename,
                        exc_info=not isinstance(exc, WorkerInternalException))
                    # restart worker
                    await self.worker.close()
                    self.worker = Worker(self.worker_handlers)
            if de.is_dir():
                subentries = await self._scan(
                    root, os.path.join(subdir, de.name))
                entries = {de.name + "/" + k: v for k, v in subentries.items()}
                entry_dict.update(entries)
        return entry_dict

    async def scan(self, root):
        self.worker = Worker(self.worker_handlers)
        try:
            r = await self._scan(root)
        finally:
            await self.worker.close()
        return r


class ExperimentDB:
    def __init__(self, repo_backend, worker_handlers):
        self.repo_backend = repo_backend
        self.worker_handlers = worker_handlers

        self.cur_rev = self.repo_backend.get_head_rev()
        self.repo_backend.request_rev(self.cur_rev)
        self.explist = Notifier(dict())
        self._scanning = False

        self.status = Notifier({
            "scanning": False,
            "cur_rev": self.cur_rev
        })

    def close(self):
        # The object cannot be used anymore after calling this method.
        self.repo_backend.release_rev(self.cur_rev)

    async def scan_repository(self, new_cur_rev=None):
        if self._scanning:
            return
        self._scanning = True
        self.status["scanning"] = True
        try:
            if new_cur_rev is None:
                new_cur_rev = self.repo_backend.get_head_rev()
            wd, _ = self.repo_backend.request_rev(new_cur_rev)
            self.repo_backend.release_rev(self.cur_rev)
            self.cur_rev = new_cur_rev
            self.status["cur_rev"] = new_cur_rev
            t1 = time.monotonic()
            new_explist = await _RepoScanner(self.worker_handlers).scan(wd)
            logger.info("repository scan took %d seconds", time.monotonic()-t1)
            update_from_dict(self.explist, new_explist)
        finally:
            self._scanning = False
            self.status["scanning"] = False

    def scan_repository_async(self, new_cur_rev=None):
        asyncio.ensure_future(
            exc_to_warning(self.scan_repository(new_cur_rev)))

    async def examine(self, filename, use_repository=True, revision=None):
        if use_repository:
            if revision is None:
                revision = self.cur_rev
            wd, _ = self.repo_backend.request_rev(revision)
            filename = os.path.join(wd, filename)
        worker = Worker(self.worker_handlers)
        try:
            description = await worker.examine("examine", filename)
        finally:
            await worker.close()
        if use_repository:
            self.repo_backend.release_rev(revision)
        return description

    def list_directory(self, directory):
        r = []
        prefix = ""
        if not directory:
            if os.name == "nt":
                drives = get_windows_drives()
                return [drive + ":\\" for drive in drives]
            else:
                directory = "/"
                prefix = "/"
        for de in os.scandir(directory):
            if de.is_dir():
                r.append(prefix + de.name + os.path.sep)
            else:
                r.append(prefix + de.name)
        return r


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
