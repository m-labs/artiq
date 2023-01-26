"""Tests for artiq_client functionality"""

import subprocess
import sys
import os
import unittest
import re
from tempfile import TemporaryDirectory
from pygit2 import init_repository, Signature

EXPERIMENT_CONTENT = """
from artiq.experiment import *
class EmptyExperiment(EnvExperiment):
    def build(self):
        pass
    def run(self):
        print("test content")
"""

DDB_CONTENT = """
device_db = {}
"""


class TestClient(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = TemporaryDirectory(prefix="test")
        self.tmp_empty_dir = TemporaryDirectory(prefix="empty_repo")
        self.exp_name = "experiment.py"
        self.exp_path = os.path.join(self.tmp_dir.name, self.exp_name)
        self.device_db_path = os.path.join(self.tmp_dir.name, "device_db.py")
        self.env = os.environ.copy()
        self.env["PYTHONUNBUFFERED"] = "1"
        with open(self.exp_path, "w") as f:
            f.write(EXPERIMENT_CONTENT)
        with open(self.device_db_path, "w") as f:
            f.write(DDB_CONTENT)

    def await_master_output_line(self):
        return self.master.stdout.readline().strip()

    def start_master(self, *args):
        self.master = subprocess.Popen([sys.executable, "-m", "artiq.frontend.artiq_master", "--device-db",
                                        self.device_db_path, *args], encoding="utf8", env=self.env,
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while self.await_master_output_line() != "ARTIQ master is now ready.":
            pass

    def wait_end_master_with_output(self):
        first_line = self.await_master_output_line()
        self.master.terminate()
        # take only stdout output because stderr is piped to it
        leftover_output = self.master.communicate()[0]
        return first_line + leftover_output

    def run_client(self, *args):
        return subprocess.run([sys.executable, "-m", "artiq.frontend.artiq_client", *args], check=True,
                              capture_output=True, env=self.env, text=True, encoding="utf8").stdout.strip()

    def check_experiment_run(self, client_output, master_output, script_name):
        pattern_rid = re.compile(r"RID: (\d+)")
        pattern_print = re.compile(r"INFO:worker\((\d+),{}\):print:test content"
                                   .format(script_name.replace(".", "\\.")))
        rid_run = int(re.findall(pattern_rid, client_output)[0])
        rid_print = int(re.findall(pattern_print, master_output)[0])
        self.assertEqual(rid_print, rid_run)
        self.assertGreaterEqual(rid_print, 0)
        self.assertNotIn("error", master_output.lower())

    def test_submit_outside_repo(self):
        self.start_master("-r", self.tmp_empty_dir.name)
        client_output = self.run_client("submit", self.exp_path)
        master_output = self.wait_end_master_with_output()
        self.check_experiment_run(client_output, master_output, self.exp_name)

    def test_submit_by_content(self):
        self.start_master("-r", self.tmp_empty_dir.name)
        client_output = self.run_client("submit", self.exp_path, "--content")
        master_output = self.wait_end_master_with_output()
        self.check_experiment_run(client_output, master_output, "<none>")

    def test_submit_by_file_repo(self):
        self.start_master("-r", self.tmp_dir.name)
        client_output = self.run_client("submit", self.exp_name, "-R")
        master_output = self.wait_end_master_with_output()
        self.check_experiment_run(client_output, master_output, self.exp_name)

    def test_submit_by_git_repo(self):
        repo = init_repository(self.tmp_dir.name)
        repo.index.add_all()
        repo.index.write()
        tree = repo.index.write_tree()
        signature = Signature("Test", "test@example.com")
        commit_msg = "Commit message"
        repo.create_commit("HEAD", signature, signature, commit_msg, tree, [])

        self.start_master("-r", self.tmp_dir.name, "-g")
        client_output = self.run_client("submit", self.exp_name, "-R")
        master_output = self.wait_end_master_with_output()
        self.check_experiment_run(client_output, master_output, self.exp_name)

    def tearDown(self):
        self.tmp_dir.cleanup()
        self.tmp_empty_dir.cleanup()
