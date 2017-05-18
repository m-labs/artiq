# Copyright (C) 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os
import sys
import unittest
import logging
import subprocess
import shlex
import time
import socket

from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.worker_db import DeviceManager, DatasetManager
from artiq.coredevice.core import CompileError
from artiq.frontend.artiq_run import DummyScheduler
from artiq.protocols.pc_rpc import AutoTarget, Client


artiq_root = os.getenv("ARTIQ_ROOT")
logger = logging.getLogger(__name__)


class GenericControllerCase(unittest.TestCase):
    def get_device_db(self):
        raise NotImplementedError

    def setUp(self):
        self.device_db = self.get_device_db()
        self.device_mgr = DeviceManager(self.device_db)
        self.controllers = {}

    def tearDown(self):
        self.device_mgr.close_devices()
        for name in list(self.controllers):
            self.stop_controller(name)

    def start_controller(self, name, sleep=1):
        if name in self.controllers:
            raise ValueError("controller `{}` already started".format(name))
        try:
            entry = self.device_db.get(name)
        except KeyError:
            raise unittest.SkipTest(
                "controller `{}` not found".format(name))
        entry["command"] = entry["command"].format(
            name=name, bind=entry["host"], port=entry["port"])
        proc = subprocess.Popen(shlex.split(entry["command"]))
        self.controllers[name] = entry, proc
        time.sleep(sleep)

    def stop_controller(self, name, default_timeout=1):
        desc, proc = self.controllers[name]
        t = desc.get("term_timeout", default_timeout)
        target_name = desc.get("target_name", None)
        if target_name is None:
            target_name = AutoTarget
        try:
            try:
                client = Client(desc["host"], desc["port"], target_name, t)
                try:
                    client.terminate()
                finally:
                    client.close_rpc()
                proc.wait(t)
                return
            except (socket.timeout, subprocess.TimeoutExpired):
                logger.warning("Controller %s failed to exit on request", name)
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                proc.wait(t)
                return
            except subprocess.TimeoutExpired:
                logger.warning("Controller %s failed to exit on terminate",
                               name)
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                proc.wait(t)
                return
            except subprocess.TimeoutExpired:
                logger.warning("Controller %s failed to die on kill", name)
        finally:
            del self.controllers[name]


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ControllerCase(GenericControllerCase):
    def get_device_db(self):
        return DeviceDB(os.path.join(artiq_root, "device_db.py"))


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self.device_db = DeviceDB(os.path.join(artiq_root, "device_db.py"))
        self.dataset_db = DatasetDB(
            os.path.join(artiq_root, "dataset_db.pyon"))
        self.device_mgr = DeviceManager(
            self.device_db, virtual_devices={"scheduler": DummyScheduler()})
        self.dataset_mgr = DatasetManager(self.dataset_db)

    def tearDown(self):
        self.device_mgr.close_devices()

    def create(self, cls, *args, **kwargs):
        try:
            exp = cls(
                (self.device_mgr, self.dataset_mgr, None),
                *args, **kwargs)
            exp.prepare()
            return exp
        except KeyError as e:
            # skip if ddb does not match requirements
            raise unittest.SkipTest(
                "device_db entry `{}` not found".format(*e.args))

    def execute(self, cls, *args, **kwargs):
        expid = {
            "file": sys.modules[cls.__module__].__file__,
            "class_name": cls.__name__,
            "arguments": dict()
        }
        self.device_mgr.virtual_devices["scheduler"].expid = expid
        try:
            exp = self.create(cls, *args, **kwargs)
            exp.run()
            exp.analyze()
            return exp
        except CompileError as error:
            # Reduce amount of text on terminal.
            raise error from None
        except Exception as exn:
            if hasattr(exn, "artiq_core_exception"):
                exn.args = "{}\n{}".format(exn.args[0],
                                           exn.artiq_core_exception),
            raise exn
