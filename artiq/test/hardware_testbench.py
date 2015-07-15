import os
import sys
import unittest
import logging

from artiq.language import *
from artiq.protocols.file_db import FlatFileDB
from artiq.master.worker_db import DeviceManager, ResultDB
from artiq.frontend.artiq_run import DummyScheduler


artiq_root = os.getenv("ARTIQ_ROOT")
logger = logging.getLogger(__name__)


def get_from_ddb(*path, default="skip"):
    if not artiq_root:
        raise unittest.SkipTest("no ARTIQ_ROOT")
    v = FlatFileDB(os.path.join(artiq_root, "ddb.pyon")).data
    try:
        for p in path:
            v = v[p]
        return v.read
    except KeyError:
        if default == "skip":
            raise unittest.SkipTest("ddb path {} not found".format(path))
        else:
            return default


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self.ddb = FlatFileDB(os.path.join(artiq_root, "ddb.pyon"))
        self.dmgr = DeviceManager(self.ddb,
            virtual_devices={"scheduler": DummyScheduler()})
        self.pdb = FlatFileDB(os.path.join(artiq_root, "pdb.pyon"))
        self.rdb = ResultDB()

    def execute(self, cls, **kwargs):
        expid = {
            "file": sys.modules[cls.__module__].__file__,
            "class_name": cls.__name__,
            "arguments": kwargs
        }
        self.dmgr.virtual_devices["scheduler"].expid = expid
        try:
            try:
                exp = cls(self.dmgr, self.pdb, self.rdb, **kwargs)
            except KeyError as e:
                # skip if ddb does not match requirements
                raise unittest.SkipTest(*e.args)
            exp.prepare()
            exp.run()
            exp.analyze()
            return exp
        finally:
            self.dmgr.close_devices()
