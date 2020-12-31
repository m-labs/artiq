import os
import sys
import subprocess
import unittest
import tempfile
from artiq.coredevice.comm_mgmt import CommMgmt
from artiq.test.hardware_testbench import ExperimentCase
from artiq.experiment import *


artiq_root = os.getenv("ARTIQ_ROOT")


class CheckLog(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        core_log("test_artiq_compile")


class TestCompile(ExperimentCase):
    def test_compile(self):
        core_addr = self.device_mgr.get_desc("core")["arguments"]["host"]
        mgmt = CommMgmt(core_addr)
        mgmt.clear_log()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(artiq_root, "device_db.py")
            subprocess.call([sys.executable, "-m", "artiq.frontend.artiq_compile", "--device-db", db_path,
                "-c", "CheckLog", "-o", os.path.join(tmp, "check_log.elf"), __file__])
            subprocess.call([sys.executable, "-m", "artiq.frontend.artiq_run", "--device-db", db_path,
                os.path.join(tmp, "check_log.elf")])
        log = mgmt.get_log()
        self.assertIn("test_artiq_compile", log)
        mgmt.close()
