from collections import OrderedDict
import importlib
import logging
import os
import time
import re

import numpy as np
import h5py

from artiq.protocols.sync_struct import Notifier
from artiq.protocols.pc_rpc import AutoTarget, Client, BestEffortClient


logger = logging.getLogger(__name__)


def _create_device(desc, device_mgr):
    ty = desc["type"]
    if ty == "local":
        module = importlib.import_module(desc["module"])
        device_class = getattr(module, desc["class"])
        return device_class(device_mgr, **desc["arguments"])
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

    def get(self, name):
        """Get the device driver or controller client corresponding to a
        device database entry."""
        if name in self.virtual_devices:
            return self.virtual_devices[name]
        if name in self.active_devices:
            return self.active_devices[name]
        else:
            desc = self.ddb.get(name)
            while isinstance(desc, str):
                # alias
                desc = self.ddb.get(desc)
            dev = _create_device(desc, self)
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


def get_last_rid():
    r = -1
    try:
        day_folders = os.listdir("results")
    except:
        return r
    day_folders = filter(lambda x: re.fullmatch('\d\d\d\d-\d\d-\d\d', x),
                         day_folders)
    for df in day_folders:
        day_path = os.path.join("results", df)
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


_type_to_hdf5 = {
    int: h5py.h5t.STD_I64BE,
    float: h5py.h5t.IEEE_F64BE,

    np.int8: h5py.h5t.STD_I8BE,
    np.int16: h5py.h5t.STD_I16BE,
    np.int32: h5py.h5t.STD_I32BE,
    np.int64: h5py.h5t.STD_I64BE,

    np.uint8: h5py.h5t.STD_U8BE,
    np.uint16: h5py.h5t.STD_U16BE,
    np.uint32: h5py.h5t.STD_U32BE,
    np.uint64: h5py.h5t.STD_U64BE,

    np.float16: h5py.h5t.IEEE_F16BE,
    np.float32: h5py.h5t.IEEE_F32BE,
    np.float64: h5py.h5t.IEEE_F64BE
}

def result_dict_to_hdf5(f, rd):
    for name, data in rd.items():
        flag = None
        # beware: isinstance(True/False, int) == True
        if isinstance(data, bool):
            data = np.int8(data)
            flag = "py_bool"
        elif isinstance(data, int):
            data = np.int64(data)
            flag = "py_int"

        if isinstance(data, np.ndarray):
            dataset = f.create_dataset(name, data=data)
        else:
            ty = type(data)
            if ty is str:
                ty_h5 = "S{}".format(len(data))
                data = data.encode()
            else:
                try:
                    ty_h5 = _type_to_hdf5[ty]
                except KeyError:
                    raise TypeError("Type {} is not supported for HDF5 output"
                                    .format(ty)) from None
            dataset = f.create_dataset(name, (), ty_h5)
            dataset[()] = data

        if flag is not None:
            dataset.attrs[flag] = np.int8(1)


class DatasetManager:
    def __init__(self, ddb):
        self.broadcast = Notifier(dict())
        self.local = dict()

        self.ddb = ddb
        self.broadcast.publish = ddb.update

    def set(self, key, value, broadcast=False, persist=False, save=True):
        if persist:
            broadcast = True
        r = None
        if broadcast:
            self.broadcast[key] = (persist, value)
            r = self.broadcast[key][1]
        if save:
            self.local[key] = value
        return r

    def get(self, key):
        try:
            return self.local[key]
        except KeyError:
            pass
        return self.ddb.get(key)

    def write_hdf5(self, f):
        result_dict_to_hdf5(f, self.local)
