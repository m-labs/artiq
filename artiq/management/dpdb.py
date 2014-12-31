from collections import OrderedDict
import importlib

from artiq.language.context import *
from artiq.management import pyon
from artiq.management.sync_struct import Notifier


def create_device(desc, mvs):
    module = importlib.import_module(desc["module"])
    device_class = getattr(module, desc["class"])
    return device_class(mvs, **desc["parameters"])


class DeviceParamSupplier:
    """Supplies devices and parameters to AutoContext objects.

    """
    def __init__(self, req_device, req_parameter):
        self.req_device = req_device
        self.req_parameter = req_parameter
        self.active_devices = OrderedDict()

    def get_missing_value(self, name, kind, requester):
        if isinstance(kind, Device):
            if name in self.active_devices:
                return self.active_devices[name]
            else:
                try:
                    desc = self.req_device(name)
                except KeyError:
                    raise KeyError(
                        "Unknown device '{}' of type '{}' requested by {}"
                        .format(name, kind.type_hint, requester))
                try:
                    while isinstance(desc, str):
                        # alias
                        desc = self.req_device(desc)
                except KeyError:
                    raise KeyError(
                        "Unknown alias '{}' for device '{}' of type '{}'"
                        " requested by {}"
                        .format(desc, name, kind.type_hint, requester))
                dev = create_device(desc, self)
                self.active_devices[name] = dev
                return dev
        elif isinstance(kind, Parameter):
            try:
                return self.req_parameter(name)
            except KeyError:
                if kind.default is not NoDefault:
                    return kind.default
                else:
                    raise KeyError("Unknown parameter: " + name)
        else:
            raise NotImplementedError

    def close(self):
        for dev in reversed(list(self.active_devices.values())):
            if hasattr(dev, "close"):
                dev.close()
        self.active_devices = OrderedDict()


class DeviceParamDB:
    def __init__(self, ddb_file, pdb_file):
        self.ddb_file = ddb_file
        self.pdb_file = pdb_file
        self.ddb = Notifier(pyon.load_file(self.ddb_file))
        self.pdb = Notifier(pyon.load_file(self.pdb_file))

    def save_ddb(self):
        pyon.store_file(self.ddb_file, self.ddb)

    def save_pdb(self):
        pyon.store_file(self.pdb_file, self.pdb)

    def req_device(self, name):
        return self.ddb.backing_struct[name]

    def set_device(self, name, description):
        self.ddb[name] = description
        self.save_ddb()

    def del_device(self, name):
        del self.ddb[name]
        self.save_ddb()

    def req_parameter(self, name):
        return self.pdb.backing_struct[name]

    def set_parameter(self, name, value):
        self.pdb[name] = value
        self.save_pdb()

    def del_parameter(self, name):
        del self.pdb[name]
        self.save_pdb()
