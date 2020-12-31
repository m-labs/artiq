# Copyright (C) 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os
import sys
import unittest
import logging

from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.worker_db import DeviceManager, DatasetManager, DeviceError
from artiq.coredevice.core import CompileError
from artiq.frontend.artiq_run import DummyScheduler


artiq_root = os.getenv("ARTIQ_ROOT")
logger = logging.getLogger(__name__)


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
                (self.device_mgr, self.dataset_mgr, None, {}),
                *args, **kwargs)
        except DeviceError as e:
            # skip if ddb does not match requirements
            raise unittest.SkipTest(
                "test device not available: `{}`".format(*e.args))
        exp.prepare()
        return exp

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
