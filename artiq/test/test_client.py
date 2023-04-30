"""Tests for artiq_client functionality"""

import subprocess
import sys
import os
import unittest
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


def get_env():
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return env


class TestClient(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = TemporaryDirectory(prefix="artiq_client_test")
        self.tmp_empty_dir = TemporaryDirectory(prefix="artiq_empty_repo")
        self.exp_name = "experiment.py"
        self.exp_path = os.path.join(self.tmp_dir.name, self.exp_name)
        self.device_db_path = os.path.join(self.tmp_dir.name, "device_db.py")
        with open(self.exp_path, "w") as f:
            f.write(EXPERIMENT_CONTENT)
        with open(self.device_db_path, "w") as f:
            f.write(DDB_CONTENT)

    def start_master(self, *args):
        self.master = subprocess.Popen([sys.executable, "-m", "artiq.frontend.artiq_master", "--device-db",
                                        self.device_db_path, *args], encoding="utf8", env=get_env(),
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while self.master.stdout.readline().strip() != "ARTIQ master is now ready.":
            pass

    def check_and_terminate_master(self):
        while not ("test content" in self.master.stdout.readline()):
            pass
        self.run_client("terminate")
        self.assertEqual(self.master.wait(), 0)
        self.master.stdout.close()

    @staticmethod
    def run_client(*args):
        subprocess.run([sys.executable, "-m", "artiq.frontend.artiq_client", *args], check=True,
                       capture_output=True, env=get_env(), text=True, encoding="utf8").check_returncode()

    def test_submit_outside_repo(self):
        self.start_master("-r", self.tmp_empty_dir.name)
        self.run_client("submit", self.exp_path)
        self.check_and_terminate_master()

    def test_submit_by_content(self):
        self.start_master("-r", self.tmp_empty_dir.name)
        self.run_client("submit", self.exp_path, "--content")
        self.check_and_terminate_master()

    def test_submit_by_file_repo(self):
        self.start_master("-r", self.tmp_dir.name)
        self.run_client("submit", self.exp_name, "-R")
        self.check_and_terminate_master()

    def test_submit_by_git_repo(self):
        repo = init_repository(self.tmp_dir.name)
        repo.index.add_all()
        repo.index.write()
        tree = repo.index.write_tree()
        signature = Signature("Test", "test@example.com")
        commit_msg = "Commit message"
        repo.create_commit("HEAD", signature, signature, commit_msg, tree, [])

        self.start_master("-r", self.tmp_dir.name, "-g")
        self.run_client("submit", self.exp_name, "-R")
        self.check_and_terminate_master()

    def tearDown(self):
        self.tmp_dir.cleanup()
        self.tmp_empty_dir.cleanup()
