from collections import OrderedDict
import importlib
import logging
import os
import time
import re

import numpy
import h5py

from artiq.protocols.sync_struct import Notifier
from artiq.protocols.pc_rpc import Client, BestEffortClient


logger = logging.getLogger(__name__)


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
                rid = int(m.group(1))
                if rid > r:
                    r = rid
    return r


_type_to_hdf5 = {
    int: h5py.h5t.STD_I64BE,
    float: h5py.h5t.IEEE_F64BE
}

def result_dict_to_hdf5(f, rd):
    for name, data in rd.items():
        if isinstance(data, list):
            el_ty = type(data[0])
            for d in data:
                if type(d) != el_ty:
                    raise TypeError("All list elements must have the same"
                                    " type for HDF5 output")
            try:
                el_ty_h5 = _type_to_hdf5[el_ty]
            except KeyError:
                raise TypeError("List element type {} is not supported for"
                                " HDF5 output".format(el_ty))
            dataset = f.create_dataset(name, (len(data), ), el_ty_h5)
            dataset[:] = data
        elif isinstance(data, numpy.ndarray):
            f.create_dataset(name, data=data)
        else:
            ty = type(data)
            try:
                ty_h5 = _type_to_hdf5[ty]
            except KeyError:
                raise TypeError("Type {} is not supported for HDF5 output"
                                .format(ty))
            dataset = f.create_dataset(name, (), ty_h5)
            dataset[()] = data


class ResultDB:
    def __init__(self):
        self.rt = Notifier(dict())
        self.nrt = dict()

    def get(self, key):
        try:
            return self.nrt[key]
        except KeyError:
            return self.rt[key].read

    def write_hdf5(self, f):
        result_dict_to_hdf5(f, self.rt.read)
        result_dict_to_hdf5(f, self.nrt)


def _create_device(desc, dmgr):
    ty = desc["type"]
    if ty == "local":
        module = importlib.import_module(desc["module"])
        device_class = getattr(module, desc["class"])
        return device_class(dmgr, **desc["arguments"])
    elif ty == "controller":
        if desc["best_effort"]:
            cl = BestEffortClient
        else:
            cl = Client
        return cl(desc["host"], desc["port"], desc["target_name"])
    else:
        raise ValueError("Unsupported type in device DB: " + ty)


class DeviceManager:
    """Handles creation and destruction of local device drivers and controller
    RPC clients."""
    def __init__(self, ddb, virtual_devices=dict()):
        self.ddb = ddb
        self.virtual_devices = virtual_devices
        self.active_devices = OrderedDict()

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
