import os, shutil
import subprocess
import unittest
import tempfile
from artiq.coredevice.comm_mgmt import CommMgmt
from artiq.test.hardware_testbench import ExperimentCase
from artiq.experiment import *


class LOG(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        self.core.reset()
        core_log("blahblah123")



class TestCompile(ExperimentCase):
    def test_compile(self):
        core_addr = self.device_mgr.get_desc("core")["arguments"]["host"]
        mgmt = CommMgmt(core_addr)
        mgmt.clear_log()
        subprocess.call(["artiq_compile", "-e", "LOG", "-o", "hehe.elf", "test_compile.py"])
        subprocess.call(["artiq_run", "hehe.elf"]) 
        with tempfile.TemporaryDirectory() as tmp:
            shutil.move(os.getcwd() + '\hehe.elf', tmp + '\hehe.elf')
        log = mgmt.get_log()
        self.assertIn("blahblah123", log)
        mgmt.close()