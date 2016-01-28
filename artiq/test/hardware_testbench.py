# Copyright (C) 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os
import sys
import unittest
import logging
import subprocess
import shlex
import time

from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.worker_db import DeviceManager, DatasetManager
from artiq.coredevice.core import CompileError
from artiq.frontend.artiq_run import DummyScheduler


artiq_root = os.getenv("ARTIQ_ROOT")
logger = logging.getLogger(__name__)


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ControllerCase(unittest.TestCase):
    def setUp(self):
        self.device_db = DeviceDB(os.path.join(artiq_root, "device_db.pyon"))
        self.device_mgr = DeviceManager(self.device_db)
        self.addCleanup(self.device_mgr.close_devices)
        self.controllers = {}

    def tearDown(self):
        self.stop_controllers()

    def start_controller(self, name, sleep=1):
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

    def stop_controllers(self):
        for entry, proc in self.controllers.values():
            proc.terminate()
        for name in list(self.controllers):
            entry, proc = self.controllers[name]
            try:
                proc.wait(entry.get("term_timeout"))
            except TimeoutError:
                proc.kill()
                proc.wait(entry.get("term_timeout"))
            del self.controllers[name]


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self.device_db = DeviceDB(os.path.join(artiq_root, "device_db.pyon"))
        self.dataset_db = DatasetDB(
            os.path.join(artiq_root, "dataset_db.pyon"))
        self.device_mgr = DeviceManager(
            self.device_db, virtual_devices={"scheduler": DummyScheduler()})
        self.dataset_mgr = DatasetManager(self.dataset_db)

    def create(self, cls, **kwargs):
        try:
            exp = cls(self.device_mgr, self.dataset_mgr, **kwargs)
            exp.prepare()
            return exp
        except KeyError as e:
            # skip if ddb does not match requirements
            raise unittest.SkipTest(*e.args)

    def execute(self, cls, *args, **kwargs):
        expid = {
            "file": sys.modules[cls.__module__].__file__,
            "class_name": cls.__name__,
            "arguments": kwargs
        }
        self.device_mgr.virtual_devices["scheduler"].expid = expid
        try:
            exp = self.create(cls, **kwargs)
            exp.run()
            exp.analyze()
            return exp
        except CompileError as error:
            # Reduce amount of text on terminal.
            raise error from None
        finally:
            self.device_mgr.close_devices()
