import asyncio

import lmdb

from sipyco.sync_struct import (Notifier, process_mod, ModAction,
                                update_from_dict)
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

    def get_satellite_cpu_target(self, destination):
        return self.data.raw_view["satellite_cpu_targets"][destination]


class DatasetDB(TaskObject):
    def __init__(self, persist_file, autosave_period=30):
        self.persist_file = persist_file
        self.autosave_period = autosave_period

        self.lmdb = lmdb.open(persist_file, subdir=False, map_size=2**30)
        data = dict()
        with self.lmdb.begin() as txn:
            for key, value_and_metadata in txn.cursor():
                value, metadata = pyon.decode(value_and_metadata.decode())
                data[key.decode()] = (True, value, metadata)
        self.data = Notifier(data)
        self.pending_keys = set()

    def close_db(self):
        self.lmdb.close()

    def save(self):
        with self.lmdb.begin(write=True) as txn:
            for key in self.pending_keys:
                if (key not in self.data.raw_view
                        or not self.data.raw_view[key][0]):
                    txn.delete(key.encode())
                else:
                    value_and_metadata = (self.data.raw_view[key][1],
                                          self.data.raw_view[key][2])
                    txn.put(key.encode(),
                            pyon.encode(value_and_metadata).encode())
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

    def get_metadata(self, key):
        return self.data.raw_view[key][2]

    def update(self, mod):
        if mod["path"]:
            key = mod["path"][0]
        else:
            assert (mod["action"] == ModAction.setitem.value
                    or mod["action"] == ModAction.delitem.value)
            key = mod["key"]
        self.pending_keys.add(key)
        process_mod(self.data, mod)

    # convenience functions (update() can be used instead)
    def set(self, key, value, persist=None, metadata=None):
        if persist is None:
            if key in self.data.raw_view:
                persist = self.data.raw_view[key][0]
            else:
                persist = False
        if metadata is None:
            if key in self.data.raw_view:
                metadata = self.data.raw_view[key][2]
            else:
                metadata = {}
        self.data[key] = (persist, value, metadata)
        self.pending_keys.add(key)

    def delete(self, key):
        del self.data[key]
        self.pending_keys.add(key)
    #


class InteractiveArgDB:
    def __init__(self):
        self.pending = Notifier(dict())
        self.futures = dict()

    async def get(self, request, arglist_desc, title):
        self.pending[request] = {"title": title, "arglist_desc": arglist_desc}
        self.futures[request] = asyncio.get_running_loop().create_future()
        try:
            value = await self.futures[request]
        finally:
            del self.pending[request]
            del self.futures[request]
        return value

    def supply(self, request, values):
        # quick sanity checks
        if request not in self.futures or self.futures[request].done():
            raise ValueError("no experiment with this RID and pipeline is "
                             "waiting for interactive arguments")
        if {i[0] for i in self.pending.raw_view[request]["arglist_desc"]} != set(values.keys()):
            raise ValueError("supplied and requested keys do not match")
        self.futures[request].set_result(values)

    def cancel(self, request):
        if request not in self.futures or self.futures[request].done():
            raise ValueError("no experiment with this RID and pipeline is "
                             "waiting for interactive arguments")
        self.futures[request].set_result(None)
