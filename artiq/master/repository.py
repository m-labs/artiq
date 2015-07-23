import os
import logging
import asyncio

from artiq.protocols.sync_struct import Notifier
from artiq.master.worker import Worker


logger = logging.getLogger(__name__)


@asyncio.coroutine
def _scan_experiments(log):
    r = dict()
    for f in os.listdir("repository"):
        if f.endswith(".py"):
            try:
                full_name = os.path.join("repository", f)
                worker = Worker({"log": lambda message: log("scan", message)})
                try:
                    description = yield from worker.examine(full_name)
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
                        "file": full_name,
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
    def __init__(self, log_fn):
        self.explist = Notifier(dict())
        self._scanning = False
        self.log_fn = log_fn

    @asyncio.coroutine
    def scan(self):
        if self._scanning:
            return
        self._scanning = True
        new_explist = yield from _scan_experiments(self.log_fn)
        _sync_explist(self.explist, new_explist)
        self._scanning = False

    def scan_async(self):
        asyncio.async(self.scan())
