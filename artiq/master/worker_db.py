"""Client-side interfaces to the master databases (devices, datasets).

These artefacts are intended for out-of-process use (i.e. from workers or the
standalone command line tools).
"""

from operator import setitem
from collections import OrderedDict
import importlib
import logging

from artiq.protocols.sync_struct import Notifier
from artiq.protocols.pc_rpc import AutoTarget, Client, BestEffortClient


logger = logging.getLogger(__name__)


class DummyDevice:
    pass


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
    elif ty == "dummy":
        return DummyDevice()
    else:
        raise ValueError("Unsupported type in device DB: " + ty)


class DeviceError(Exception):
    pass


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
            try:
                desc = self.get_desc(name)
            except Exception as e:
                raise DeviceError("Failed to get description of device '{}'"
                                  .format(name)) from e
            try:
                dev = _create_device(desc, self)
            except Exception as e:
                raise DeviceError("Failed to create device '{}'"
                                  .format(name)) from e
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


class DatasetManager:
    def __init__(self, ddb):
        self._broadcaster = Notifier(dict())
        self.local = dict()
        self.archive = dict()

        self.ddb = ddb
        self._broadcaster.publish = ddb.update

    def set(self, key, value, broadcast=False, persist=False, archive=True):
        if key in self.archive:
            logger.warning("Modifying dataset '%s' which is in archive, "
                           "archive will remain untouched",
                           key, stack_info=True)

        if persist:
            broadcast = True

        if broadcast:
            self._broadcaster[key] = persist, value
        elif key in self._broadcaster.raw_view:
            del self._broadcaster[key]

        if archive:
            self.local[key] = value
        elif key in self.local:
            del self.local[key]

    def mutate(self, key, index, value):
        target = None
        if key in self.local:
            target = self.local[key]
        if key in self._broadcaster.raw_view:
            if target is not None:
                assert target is self._broadcaster.raw_view[key][1]
            target = self._broadcaster[key][1]
        if target is None:
            raise KeyError("Cannot mutate non-existing dataset")

        if isinstance(index, tuple):
            if isinstance(index[0], tuple):
                index = tuple(slice(*e) for e in index)
            else:
                index = slice(*index)
        setitem(target, index, value)

    def get(self, key, archive=False):
        if key in self.local:
            return self.local[key]
        
        data = self.ddb.get(key)
        if archive:
            if key in self.archive:
                logger.warning("Dataset '%s' is already in archive, "
                               "overwriting", key, stack_info=True)
            self.archive[key] = data
        return data

    def write_hdf5(self, f):
        datasets_group = f.create_group("datasets")
        for k, v in self.local.items():
            datasets_group[k] = v

        archive_group = f.create_group("archive")
        for k, v in self.archive.items():
            archive_group[k] = v
