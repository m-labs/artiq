"""Autotests for artiq_client functionality"""

import subprocess
import sys
import os
import shutil
import unittest
import re
import logging
from time import sleep
from pygit2 import init_repository, Signature

artiq_root = os.getenv("ARTIQ_ROOT")

experiment_content = """
from artiq.experiment import *
class EmptyExperiment(EnvExperiment):
    def build(self):
        self.setattr_device("core")
    @host_only
    def run(self):
        print("test content")
        {}
""".format(
    """self._run()
    @kernel
    def _run(self):
        pass""" if artiq_root else ""
)

tmp_dir = "__tmp_test"
tmp_empty_dir = "__tmp_empty_repo"
tmp_file = "experiment.py"
tmp_path = os.path.join(tmp_dir, tmp_file)
artiq_client = "artiq.frontend.artiq_client"
artiq_master = "artiq.frontend.artiq_master"

device_db_content = """
core_addr = "192.168.1.123"
device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": core_addr, "ref_period": 1e-09, "target": "rv32g"},
    },
}
"""

device_db_path = os.path.join(artiq_root, "device_db.py") if artiq_root else os.path.join(tmp_dir, "device_db.py")

schedule_exp_content = """
from artiq.experiment import *
class ScheduleTest(EnvExperiment):
    def build(self):
        self._scheduler = self.get_device("scheduler")
    def run(self):
        new_expid = {{
            "file": "{}",
            "class_name": "EmptyExperiment",
            "arguments": {{}},
            "log_level": 30,
        }}
        self._scheduler.submit(pipeline_name="main", expid=new_expid)
""".format(tmp_path)

schedule_exp_path = "__schedule_exp.py"


class TestClient(unittest.TestCase):
    def setUp(self):
        os.mkdir(tmp_dir)
        os.mkdir(tmp_empty_dir)
        with open(tmp_path, "w") as f:
            f.write(experiment_content)
        if not artiq_root:
            with open(device_db_path, "w") as f:
                f.write(device_db_content)
        with open(schedule_exp_path, "w") as f:
            f.write(schedule_exp_content)

    def start_master(self, *args):
        self.master = subprocess.Popen([sys.executable, "-m", artiq_master, "--device-db", device_db_path, *args],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        sleep(0.1)

    def end_master(self):
        # this is more reliable method of getting output,
        # than trying to poll process for existing output
        self.master.terminate()
        return self.master.communicate()[0].decode("utf8")

    def check_rid(self, client_out, client_err, master_output, script_name, rid_diff=0):
        pattern_rid = re.compile(r"RID: (\d+)")
        pattern_print = re.compile(r"INFO:worker\((\d+),{}\):print:test content"
                                   .format(script_name.replace(".", "\\.")))
        logging.debug("out: `{}`\nerr: `{}`\nmaster: `{}`".format(client_out, client_err, master_output))
        rid_run = int(re.findall(pattern_rid, client_out)[0])
        rid_print = int(re.findall(pattern_print, master_output)[0])
        self.assertEqual(rid_print - rid_run, rid_diff)
        self.assertGreaterEqual(rid_print, 0)
        self.assertGreaterEqual(rid_run, 0)
        self.assertEqual(master_output.count("ARTIQ master is now ready."), 1)
        self.assertEqual(master_output.lower().count("error"), 0)

    def test_submit_outside_repo(self):
        self.start_master("-r", tmp_empty_dir)
        completed = subprocess.run([sys.executable, "-m", artiq_client,
                                    "submit", tmp_path], capture_output=True)
        sleep(0.5)
        output = self.end_master()
        self.check_rid(completed.stdout.decode("utf8").strip(),
                       completed.stderr.decode("utf8").strip(), output, tmp_file)

    @unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
    def test_schedule_submit(self):
        self.start_master("-r", tmp_dir)
        completed = subprocess.run([sys.executable, "-m", artiq_client,
                                    "submit", schedule_exp_path], capture_output=True)
        sleep(0.5)
        output = self.end_master()
        self.check_rid(completed.stdout.decode("utf8").strip(),
                       completed.stderr.decode("utf8").strip(), output, tmp_file, 1)

    def test_submit_by_content(self):
        self.start_master("-r", tmp_empty_dir)
        completed = subprocess.run([sys.executable, "-m", artiq_client,
                                    "submit", tmp_path, "--content"], capture_output=True)
        sleep(0.5)
        output = self.end_master()
        self.check_rid(completed.stdout.decode("utf8").strip(),
                       completed.stderr.decode("utf8").strip(), output, "<none>")

    def test_submit_by_file_repo(self):
        self.start_master("-r", tmp_dir)
        completed = subprocess.run([sys.executable, "-m", artiq_client,
                                    "submit", tmp_file, "-R"], capture_output=True)
        sleep(0.5)
        output = self.end_master()
        self.check_rid(completed.stdout.decode("utf8").strip(),
                       completed.stderr.decode("utf8").strip(), output, tmp_file)

    def test_submit_by_git_repo(self):
        repo = init_repository(tmp_dir)
        repo.index.add_all()
        repo.index.write()
        tree = repo.index.write_tree()
        signature = Signature("Test", "test@example.com")
        commit_msg = "Commit message"
        repo.create_commit("HEAD", signature, signature, commit_msg, tree, [])

        self.start_master("-r", tmp_dir, "-g")
        completed = subprocess.run([sys.executable, "-m", artiq_client,
                                    "submit", tmp_file, "-R"], capture_output=True)
        sleep(0.5)
        output = self.end_master()
        self.check_rid(completed.stdout.decode("utf8").strip(),
                       completed.stderr.decode("utf8").strip(), output, tmp_file)

    def tearDown(self):
        shutil.rmtree(tmp_dir)
        shutil.rmtree(tmp_empty_dir)
        os.remove(schedule_exp_path)
