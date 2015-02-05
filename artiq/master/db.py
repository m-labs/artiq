from collections import OrderedDict
import importlib

import numpy
import h5py

from artiq.protocols.sync_struct import Notifier
from artiq.protocols.pc_rpc import Client


_type_to_hdf5 = {
    int: h5py.h5t.STD_I64BE,
    float: h5py.h5t.IEEE_F64BE
}

def _result_dict_to_hdf5(f, rd):
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
    def __init__(self, realtime_results):
        self.realtime_data = Notifier({x: [] for x in realtime_results})
        self.data = Notifier(dict())

    def _request(self, name):
        try:
            return self.realtime_data[name]
        except KeyError:
            try:
                return self.data[name]
            except KeyError:
                self.data[name] = []
                return self.data[name]

    def request(self, name):
        r = self._request(name)
        r.kernel_attr_init = False
        return r

    def set(self, name, value):
        if name in self.realtime_data.read:
            self.realtime_data[name] = value
        else:
            self.data[name] = value

    def write_hdf5(self, f):
        _result_dict_to_hdf5(f, self.realtime_data.read)
        _result_dict_to_hdf5(f, self.data.read)


def _create_device(desc, dbh):
    ty = desc["type"]
    if ty == "local":
        module = importlib.import_module(desc["module"])
        device_class = getattr(module, desc["class"])
        return device_class(dbh, **desc["arguments"])
    elif ty == "controller":
        return Client(desc["host"], desc["port"], desc["target_name"])
    else:
        raise ValueError("Unsupported type in device DB: " + ty)


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
            if isinstance(dev, Client):
                dev.close_rpc()
            elif hasattr(dev, "close"):
                dev.close()
