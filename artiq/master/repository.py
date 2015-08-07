import asyncio
import os
import tempfile
import shutil
import logging

from artiq.protocols.sync_struct import Notifier
from artiq.master.worker import Worker


logger = logging.getLogger(__name__)


@asyncio.coroutine
def _scan_experiments(wd, log):
    r = dict()
    for f in os.listdir(wd):
        if f.endswith(".py"):
            try:
                worker = Worker({"log": lambda message: log("scan", message)})
                try:
                    description = yield from worker.examine(os.path.join(wd, f))
                finally:
                    yield from worker.close()
                for class_name, class_desc in description.items():
                    name = class_desc["name"]
                    arguments = class_desc["arguments"]
                    if name in r:
                        logger.warning("Duplicate experiment name: '%s'", name)
                        basename = name
                        i = 1
                        while name in r:
                            name = basename + str(i)
                            i += 1
                    entry = {
                        "file": f,
                        "class_name": class_name,
                        "arguments": arguments
                    }
                    r[name] = entry
            except:
                logger.warning("Skipping file '%s'", f, exc_info=True)
    return r


def _sync_explist(target, source):
    for k in list(target.read.keys()):
        if k not in source:
            del target[k]
    for k in source.keys():
        if k not in target.read or target.read[k] != source[k]:
            target[k] = source[k]


class Repository:
    def __init__(self, backend, log_fn):
        self.backend = backend
        self.log_fn = log_fn

        self.head_rev = self.backend.get_head_rev()
        self.backend.request_rev(self.head_rev)
        self.explist = Notifier(dict())

        self._scanning = False

    @asyncio.coroutine
    def scan(self):
        if self._scanning:
            return
        self._scanning = True

        new_head_rev = self.backend.get_head_rev()
        wd = self.backend.request_rev(new_head_rev)
        self.backend.release_rev(self.head_rev)
        self.head_rev = new_head_rev
        new_explist = yield from _scan_experiments(wd, self.log_fn)

        _sync_explist(self.explist, new_explist)
        self._scanning = False

    def scan_async(self):
        asyncio.async(self.scan())


class FilesystemBackend:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def get_head_rev(self):
        return "N/A"

    def request_rev(self, rev):
        return self.root

    def release_rev(self, rev):
        pass


class _GitCheckout:
    def __init__(self, git, rev):
        self.path = tempfile.mkdtemp()
        git.checkout_tree(git.get(rev), directory=self.path)
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
        return co.path

    def release_rev(self, rev):
        co = self.checkouts[rev]
        co.ref_count -= 1
        if not co.ref_count:
            co.dispose()
            del self.checkouts[rev]
