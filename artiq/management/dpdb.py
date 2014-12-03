from collections import OrderedDict
import importlib

from artiq.language.context import *


def create_device(desc, mvs):
    module = importlib.import_module(desc["module"])
    device_class = getattr(module, desc["class"])
    return device_class(mvs, **desc["parameters"])


class DeviceParamDB:
    def __init__(self, devices, parameters):
        self.devices = devices
        self.parameters = parameters
        self.active_devices = OrderedDict()

    def get_missing_value(self, name, kind, requester):
        if isinstance(kind, Device):
            if name in self.active_devices:
                return self.active_devices[name]
            elif name in self.devices:
                desc = self.devices[name]
                while isinstance(desc, str):
                    # alias
                    desc = self.devices[desc]
                dev = create_device(desc, self)
                self.active_devices[name] = dev
                return dev
            else:
                raise KeyError("Unknown device '{}' of type '{}'"
                               " requested by {}"
                               .format(name, kind.type_hint, requester))
        elif isinstance(kind, Parameter):
            if name in self.parameters:
                return self.parameters[name]
            elif kind.default is not NoDefault:
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
