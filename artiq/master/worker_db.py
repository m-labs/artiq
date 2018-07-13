from operator import setitem
from collections import OrderedDict
import importlib
import logging
import os
import tempfile
import re

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
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False
                                         ) as f:
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
        day_folders = filter(
            lambda x: re.fullmatch("\\d\\d\\d\\d-\\d\\d-\\d\\d", x),
            day_folders)
        for df in day_folders:
            day_path = os.path.join(self.results_dir, df)
            try:
                hm_folders = os.listdir(day_path)
            except:
                continue
            hm_folders = filter(lambda x: re.fullmatch("\\d\\d(-\\d\\d)?", x),
                                hm_folders)
            for hmf in hm_folders:
                hm_path = os.path.join(day_path, hmf)
                try:
                    h5files = os.listdir(hm_path)
                except:
                    continue
                for x in h5files:
                    m = re.fullmatch(
                        "(\\d\\d\\d\\d\\d\\d\\d\\d\\d)-.*\\.h5", x)
                    if m is None:
                        continue
                    rid = int(m.group(1))
                    if rid > r:
                        r = rid
        return r


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
        self.broadcast = Notifier(dict())
        self.local = dict()
        self.archive = dict()

        self.ddb = ddb
        self.broadcast.publish = ddb.update

    def set(self, key, value, broadcast=False, persist=False, save=True):
        if key in self.archive:
            logger.warning("Modifying dataset '%s' which is in archive, "
                           "archive will remain untouched",
                           key, stack_info=True)

        if persist:
            broadcast = True
        if broadcast:
            self.broadcast[key] = persist, value
        elif key in self.broadcast.read:
            del self.broadcast[key]
        if save:
            self.local[key] = value
        elif key in self.local:
            del self.local[key]

    def mutate(self, key, index, value):
        target = None
        if key in self.local:
            target = self.local[key]
        if key in self.broadcast.read:
            if target is not None:
                assert target is self.broadcast.read[key][1]
            target = self.broadcast[key][1]
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
        else:
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
