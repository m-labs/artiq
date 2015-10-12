# Copyright (C) 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os
import sys
import unittest
import logging

from artiq.language import *
from artiq.protocols import pyon
from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.worker_db import DeviceManager, DatasetManager
from artiq.frontend.artiq_run import DummyScheduler


artiq_root = os.getenv("ARTIQ_ROOT")
logger = logging.getLogger(__name__)


def get_from_ddb(*path, default="skip"):
    if not artiq_root:
        raise unittest.SkipTest("no ARTIQ_ROOT")
    v = pyon.load_file(os.path.join(artiq_root, "device_db.pyon"))
    try:
        for p in path:
            v = v[p]
        return v.read
    except KeyError:
        if default == "skip":
            raise unittest.SkipTest("device db path {} not found".format(path))
        else:
            return default


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self.device_db = DeviceDB(os.path.join(artiq_root, "device_db.pyon"))
        self.dataset_db = DatasetDB(os.path.join(artiq_root, "dataset_db.pyon"))
        self.device_mgr = DeviceManager(self.device_db,
            virtual_devices={"scheduler": DummyScheduler()})
        self.dataset_mgr = DatasetManager(self.dataset_db)

    def execute(self, cls, **kwargs):
        expid = {
            "file": sys.modules[cls.__module__].__file__,
            "class_name": cls.__name__,
            "arguments": kwargs
        }
        self.device_mgr.virtual_devices["scheduler"].expid = expid
        try:
            try:
                exp = cls(self.device_mgr, self.dataset_mgr, **kwargs)
            except KeyError as e:
                # skip if ddb does not match requirements
                raise unittest.SkipTest(*e.args)
            exp.prepare()
            exp.run()
            exp.analyze()
            return exp
        finally:
            self.device_mgr.close_devices()
