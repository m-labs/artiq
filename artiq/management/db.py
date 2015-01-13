from collections import OrderedDict, defaultdict
import importlib
from time import time

from artiq.language.db import *
from artiq.management import pyon
from artiq.management.sync_struct import Notifier


class FlatFileDB:
    def __init__(self, filename):
        self.filename = filename
        self.data = Notifier(pyon.load_file(self.filename))
        self.hooks = []

    def save(self):
        pyon.store_file(self.filename, self.data.read)

    def request(self, name):
        return self.data.read[name]

    def set(self, name, value):
        self.data[name] = value
        self.save()
        timestamp = time()
        for hook in self.hooks:
            hook.set(timestamp, name, value)

    def delete(self, name):
        del self.data[name]
        self.save()
        timestamp = time()
        for hook in self.hooks:
            hook.delete(timestamp, name)


class SimpleHistory:
    def __init__(self, depth):
        self.depth = depth
        self.history = Notifier([])

    def set(self, timestamp, name, value):
        if len(self.history.read) >= self.depth:
            del self.history[0]
        self.history.append((timestamp, name, value))

    def delete(self, timestamp, name):
        if len(self.history.read) >= self.depth:
            del self.history[0]
        self.history.append((timestamp, name))


class ResultDB:
    def __init__(self):
        self.data = defaultdict(list)

    def request(self, name):
        return self.data[name]

    def set(self, name, value):
        self.data[name] = value


def _create_device(desc, dbh):
    module = importlib.import_module(desc["module"])
    device_class = getattr(module, desc["class"])
    return device_class(dbh, **desc["arguments"])


class DBHub:
    """Connects device, parameter and result databases to experiment.
    Handle device driver creation and destruction.

    """
    def __init__(self, ddb, pdb, rdb):
        self.ddb = ddb
        self.active_devices = OrderedDict()

        self.get_parameter = pdb.request
        self.set_parameter = pdb.set
        self.get_result = rdb.request
        self.set_result = rdb.set

    def get_device(self, name):
        if name in self.active_devices:
            return self.active_devices[name]
        else:
            desc = self.ddb.request(name)
            while isinstance(desc, str):
                # alias
                desc = self.ddb.request(desc)
            dev = _create_device(desc, self)
            self.active_devices[name] = dev
            return dev

    def close(self):
        """Closes all active devices, in the opposite order as they were
        requested.

        Do not use the same ``DBHub`` again after calling
        this function.

        """
        for dev in reversed(list(self.active_devices.values())):
            if hasattr(dev, "close"):
                dev.close()
