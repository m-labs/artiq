import asyncio

import lmdb

from sipyco.sync_struct import Notifier, process_mod, ModAction, update_from_dict
from sipyco import pyon
from sipyco.asyncio_tools import TaskObject

from artiq.tools import file_import


def device_db_from_file(filename):
    mod = file_import(filename)

    # use __dict__ instead of direct attribute access
    # for backwards compatibility of the exception interface
    # (raise KeyError and not AttributeError if device_db is missing)
    return mod.__dict__["device_db"]


class DeviceDB:
    def __init__(self, backing_file):
        self.backing_file = backing_file
        self.data = Notifier(device_db_from_file(self.backing_file))

    def scan(self):
        update_from_dict(self.data, device_db_from_file(self.backing_file))

    def get_device_db(self):
        return self.data.raw_view

    def get(self, key, resolve_alias=False):
        desc = self.data.raw_view[key]
        if resolve_alias:
            while isinstance(desc, str):
                desc = self.data.raw_view[desc]
        return desc


class DatasetDB(TaskObject):
    def __init__(self, persist_file, autosave_period=30):
        self.persist_file = persist_file
        self.autosave_period = autosave_period

        self.lmdb = lmdb.open(persist_file, subdir=False, map_size=2**30)
        data = dict()
        with self.lmdb.begin() as txn:
            for key, value in txn.cursor():
                data[key.decode()] = (True, pyon.decode(value.decode()))
        self.data = Notifier(data)
        self.pending_keys = set()

    def close_db(self):
        self.lmdb.close()

    def save(self):
        with self.lmdb.begin(write=True) as txn:
            for key in self.pending_keys:
                if key not in self.data.raw_view or not self.data.raw_view[key][0]:
                    txn.delete(key.encode())
                else:
                    txn.put(key.encode(), pyon.encode(self.data.raw_view[key][1]).encode())
        self.pending_keys.clear()

    async def _do(self):
        try:
            while True:
                await asyncio.sleep(self.autosave_period)
                self.save()
        finally:
            self.save()

    def get(self, key):
        return self.data.raw_view[key][1]

    def update(self, mod):
        if mod["path"]:
            key = mod["path"][0]
        else:
            assert(mod["action"] == ModAction.setitem.value or mod["action"] == ModAction.delitem.value)
            key = mod["key"]
        self.pending_keys.add(key)
        process_mod(self.data, mod)

    # convenience functions (update() can be used instead)
    def set(self, key, value, persist=None):
        if persist is None:
            if key in self.data.raw_view:
                persist = self.data.raw_view[key][0]
            else:
                persist = False
        self.data[key] = (persist, value)
        self.pending_keys.add(key)

    def delete(self, key):
        del self.data[key]
        self.pending_keys.add(key)
    #
