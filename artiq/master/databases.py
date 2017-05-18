import asyncio

from artiq.protocols.sync_struct import Notifier, process_mod
from artiq.protocols import pyon
from artiq.tools import TaskObject


def device_db_from_file(filename):
    glbs = dict()
    with open(filename, "r") as f:
        exec(f.read(), glbs)
    return glbs["device_db"]


class DeviceDB:
    def __init__(self, backing_file):
        self.backing_file = backing_file
        self.data = Notifier(device_db_from_file(self.backing_file))

    def scan(self):
        new_data = device_db_from_file(self.backing_file)

        for k in list(self.data.read.keys()):
            if k not in new_data:
                del self.data[k]
        for k in new_data.keys():
            if k not in self.data.read or self.data.read[k] != new_data[k]:
                self.data[k] = new_data[k]

    def get_device_db(self):
        return self.data.read

    def get(self, key):
        return self.data.read[key]


class DatasetDB(TaskObject):
    def __init__(self, persist_file, autosave_period=30):
        self.persist_file = persist_file
        self.autosave_period = autosave_period

        try:
            file_data = pyon.load_file(self.persist_file)
        except FileNotFoundError:
            file_data = dict()
        self.data = Notifier({k: (True, v) for k, v in file_data.items()})

    def save(self):
        data = {k: v[1] for k, v in self.data.read.items() if v[0]}
        pyon.store_file(self.persist_file, data)

    async def _do(self):
        try:
            while True:
                await asyncio.sleep(self.autosave_period)
                self.save()
        finally:
            self.save()

    def get(self, key):
        return self.data.read[key][1]

    def update(self, mod):
        process_mod(self.data, mod)

    # convenience functions (update() can be used instead)
    def set(self, key, value, persist=None):
        if persist is None:
            if key in self.data.read:
                persist = self.data.read[key][0]
            else:
                persist = False
        self.data[key] = (persist, value)

    def delete(self, key):
        del self.data[key]
    #
