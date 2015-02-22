import os
import time

import numpy
import h5py

from artiq.protocols.sync_struct import Notifier, process_mod


def get_hdf5_output(start_time, rid, name):
    dirname = os.path.join("results",
                           time.strftime("%Y-%m-%d", start_time),
                           time.strftime("%H-%M", start_time))
    filename = "{:09}-{}.h5".format(rid, name)
    os.makedirs(dirname, exist_ok=True)
    return h5py.File(os.path.join(dirname, filename), "w")


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


class RTResults:
    def __init__(self):
        self.groups = Notifier(dict())
        self.current_group = "default"

    def init(self, description):
        data = dict()
        for rtr in description.keys():
            if isinstance(rtr, tuple):
                for e in rtr:
                    data[e] = []
            else:
                data[rtr] = []
        self.groups[self.current_group] = {
            "description": description,
            "data": data
        }

    def update(self, mod):
        target = self.groups[self.current_group]["data"]
        process_mod(target, mod)
