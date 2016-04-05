from collections import OrderedDict
import importlib
import logging
import os
import tempfile
import time
import re

import numpy as np
import h5py

from artiq.protocols.sync_struct import Notifier
from artiq.protocols.pc_rpc import AutoTarget, Client, BestEffortClient


logger = logging.getLogger(__name__)


class RIDCounter:
    def __init__(self, cache_filename="last_rid.pyon", results_dir="results"):
        self.cache_filename = cache_filename
        self.results_dir = results_dir
        self._next_rid = self._last_rid() + 1
        logger.debug("Next RID is %d", self._next_rid)

    def get(self):
        rid = self._next_rid
        self._next_rid += 1
        self._update_cache(rid)
        return rid

    def _last_rid(self):
        try:
            rid = self._last_rid_from_cache()
        except FileNotFoundError:
            logger.debug("Last RID cache not found, scanning results")
            rid = self._last_rid_from_results()
            self._update_cache(rid)
            return rid
        else:
            logger.debug("Using last RID from cache")
            return rid

    def _update_cache(self, rid):
        contents = str(rid) + "\n"
        directory = os.path.abspath(os.path.dirname(self.cache_filename))
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as f:
            f.write(contents)
            tmpname = f.name
        os.replace(tmpname, self.cache_filename)

    def _last_rid_from_cache(self):
        with open(self.cache_filename, "r") as f:
            return int(f.read())

    def _last_rid_from_results(self):
        r = -1
        try:
            day_folders = os.listdir(self.results_dir)
        except:
            return r
        day_folders = filter(lambda x: re.fullmatch('\d\d\d\d-\d\d-\d\d', x),
                             day_folders)
        for df in day_folders:
            day_path = os.path.join(self.results_dir, df)
            try:
                minute_folders = os.listdir(day_path)
            except:
                continue
            minute_folders = filter(lambda x: re.fullmatch('\d\d-\d\d', x),
                                              minute_folders)
            for mf in minute_folders:
                minute_path = os.path.join(day_path, mf)
                try:
                    h5files = os.listdir(minute_path)
                except:
                    continue
                for x in h5files:
                    m = re.fullmatch('(\d\d\d\d\d\d\d\d\d)-.*\.h5', x)
                    if m is None:
                        continue
                    rid = int(m.group(1))
                    if rid > r:
                        r = rid
        return r


def _create_device(desc, device_mgr):
    ty = desc["type"]
    if ty == "local":
        module = importlib.import_module(desc["module"])
        device_class = getattr(module, desc["class"])
        return device_class(device_mgr, **desc.get("arguments", {}))
    elif ty == "controller":
        if desc.get("best_effort", False):
            cls = BestEffortClient
        else:
            cls = Client
        # Automatic target can be specified either by the absence of
        # the target_name parameter, or a None value.
        target_name = desc.get("target_name", None)
        if target_name is None:
            target_name = AutoTarget
        return cls(desc["host"], desc["port"], target_name)
    elif ty == "controller_aux_target":
        controller = device_mgr.get_desc(desc["controller"])
        if desc.get("best_effort", controller.get("best_effort", False)):
            cls = BestEffortClient
        else:
            cls = Client
        return cls(controller["host"], controller["port"], desc["target_name"])
    else:
        raise ValueError("Unsupported type in device DB: " + ty)


class DeviceManager:
    """Handles creation and destruction of local device drivers and controller
    RPC clients."""
    def __init__(self, ddb, virtual_devices=dict()):
        self.ddb = ddb
        self.virtual_devices = virtual_devices
        self.active_devices = OrderedDict()

    def get_device_db(self):
        """Returns the full contents of the device database."""
        return self.ddb.get_device_db()

    def get_desc(self, name):
        desc = self.ddb.get(name)
        while isinstance(desc, str):
            # alias
            desc = self.ddb.get(desc)
        return desc

    def get(self, name):
        """Get the device driver or controller client corresponding to a
        device database entry."""
        if name in self.virtual_devices:
            return self.virtual_devices[name]
        if name in self.active_devices:
            return self.active_devices[name]
        else:
            dev = _create_device(self.get_desc(name), self)
            self.active_devices[name] = dev
            return dev

    def close_devices(self):
        """Closes all active devices, in the opposite order as they were
        requested."""
        for dev in reversed(list(self.active_devices.values())):
            try:
                if isinstance(dev, (Client, BestEffortClient)):
                    dev.close_rpc()
                elif hasattr(dev, "close"):
                    dev.close()
            except Exception as e:
                logger.warning("Exception %r when closing device %r", e, dev)
        self.active_devices.clear()


def get_hdf5_output(start_time, rid, name):
    dirname = os.path.join("results",
                           time.strftime("%Y-%m-%d", start_time),
                           time.strftime("%H-%M", start_time))
    filename = "{:09}-{}.h5".format(rid, name)
    os.makedirs(dirname, exist_ok=True)
    return h5py.File(os.path.join(dirname, filename), "w")


class DatasetManager:
    def __init__(self, ddb):
        self.broadcast = Notifier(dict())
        self.local = dict()

        self.ddb = ddb
        self.broadcast.publish = ddb.update

    def set(self, key, value, broadcast=False, persist=False, save=True):
        if persist:
            broadcast = True
        if broadcast:
            self.broadcast[key] = persist, value
        if save:
            self.local[key] = value

    def mutate(self, key, index, value):
        target = None
        if key in self.local:
            target = self.local[key]
        if key in self.broadcast.read:
            target = self.broadcast[key][1]
        if target is None:
            raise KeyError("Cannot mutate non-existing dataset")
        target[index] = value

    def get(self, key):
        if key in self.local:
            return self.local[key]
        else:
            return self.ddb.get(key)

    def write_hdf5(self, f):
        g = f.create_group("datasets")
        for k, v in self.local.items():
            g[k] = v
