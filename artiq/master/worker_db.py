"""Client-side interfaces to the master databases (devices, datasets).

These artefacts are intended for out-of-process use (i.e. from workers or the
standalone command line tools).
"""

from operator import setitem
import importlib
import logging

from sipyco.sync_struct import Notifier
from sipyco.pc_rpc import AutoTarget, Client, BestEffortClient


logger = logging.getLogger(__name__)


class DummyDevice:
    pass


def _create_device(desc, device_mgr, argument_overrides):
    ty = desc["type"]
    if ty == "local":
        module = importlib.import_module(desc["module"])
        device_class = getattr(module, desc["class"])
        arguments = desc.get("arguments", {}) | argument_overrides
        return device_class(device_mgr, **arguments)
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
        self.active_devices = []
        self.devarg_override = {}

    def get_device_db(self):
        """Returns the full contents of the device database."""
        return self.ddb.get_device_db()

    def get_desc(self, name):
        return self.ddb.get(name, resolve_alias=True)

    def get(self, name):
        """Get the device driver or controller client corresponding to a
        device database entry."""
        if name in self.virtual_devices:
            return self.virtual_devices[name]

        try:
            desc = self.get_desc(name)
        except Exception as e:
            raise DeviceError("Failed to get description of device '{}'"
                              .format(name)) from e

        for existing_desc, existing_dev in self.active_devices:
            if desc == existing_desc:
                return existing_dev

        try:
            dev = _create_device(desc, self, self.devarg_override.get(name, {}))
        except Exception as e:
            raise DeviceError("Failed to create device '{}'"
                              .format(name)) from e
        self.active_devices.append((desc, dev))
        return dev

    def notify_run_end(self):
        """Sends a "end of Experiment run stage" notification to
        all active devices."""
        for _desc, dev in self.active_devices:
            if hasattr(dev, "notify_run_end"):
                dev.notify_run_end()

    def close_devices(self):
        """Closes all active devices, in the opposite order as they were
        requested."""
        for _desc, dev in reversed(self.active_devices):
            try:
                if isinstance(dev, (Client, BestEffortClient)):
                    dev.close_rpc()
                elif hasattr(dev, "close"):
                    dev.close()
            except:
                logger.warning("Exception raised when closing device %r:",
                               dev, exc_info=True)
        self.active_devices.clear()


class DatasetManager:
    def __init__(self, ddb):
        self._broadcaster = Notifier(dict())
        self.local = dict()
        self.archive = dict()
        self.metadata = dict()

        self.ddb = ddb
        self._broadcaster.publish = ddb.update

    def set(self, key, value, metadata, broadcast, persist, archive):
        if persist:
            broadcast = True

        if not (broadcast or archive):
            logger.warning(f"Dataset '{key}' will not be stored. Both 'broadcast' and 'archive' are set to False.")

        if broadcast:
            self._broadcaster[key] = persist, value, metadata
        elif key in self._broadcaster.raw_view:
            del self._broadcaster[key]

        if archive:
            self.local[key] = value
        elif key in self.local:
            del self.local[key]
        
        self.metadata[key] = metadata

    def _get_mutation_target(self, key):
        target = self.local.get(key, None)
        if key in self._broadcaster.raw_view:
            if target is not None:
                assert target is self._broadcaster.raw_view[key][1]
            return self._broadcaster[key][1]
        if target is None:
            raise KeyError("Cannot mutate nonexistent dataset '{}'".format(key))
        return target

    def mutate(self, key, index, value):
        target = self._get_mutation_target(key)
        if isinstance(index, tuple):
            if isinstance(index[0], tuple):
                index = tuple(slice(*e) for e in index)
            else:
                index = slice(*index)
        setitem(target, index, value)

    def append_to(self, key, value):
        self._get_mutation_target(key).append(value)

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

    def get_metadata(self, key):
        if key in self.metadata:
            return self.metadata[key]
        return self.ddb.get_metadata(key)

    def write_hdf5(self, f):
        datasets_group = f.create_group("datasets")
        for k, v in self.local.items():
            m = self.metadata.get(k, {})
            _write(datasets_group, k, v, m)

        archive_group = f.create_group("archive")
        for k, v in self.archive.items():
            m = self.metadata.get(k, {})
            _write(archive_group, k, v, m)


def _write(group, k, v, m):
    # Add context to exception message when the user writes a dataset that is
    # not representable in HDF5.
    try:
        group[k] = v
        for key, val in m.items():
            group[k].attrs[key] = val
    except TypeError as e:
        raise TypeError("Error writing dataset '{}' of type '{}': {}".format(
            k, type(v), e))
