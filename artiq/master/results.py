import os
import time
import re

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
