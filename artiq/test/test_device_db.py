"""Test device DB interface"""

import os
import unittest
import tempfile
from pathlib import Path

from artiq.master.databases import DeviceDB
from artiq.tools import file_import


DUMMY_DDB_FILE = """
device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": "::1", "ref_period": 1e-09},
    },

    "core_alias": "core",
    "unresolved_alias": "dummy",
}
"""

# tempfile.NamedTemporaryFile:
# use delete=False and manual cleanup
# for Windows compatibility


class TestDeviceDBImport(unittest.TestCase):
    def test_no_device_db_in_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".py", delete=False) as f:
            print(f.name)
            print("", file=f, flush=True)

            with self.assertRaisesRegex(KeyError, "device_db"):
                DeviceDB(f.name)

        os.unlink(f.name)

    def test_import_same_level(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # make sure both files land in the same directory
            # tempfiles are cleanup together with tmpdir
            args = dict(mode="w+", suffix=".py", dir=tmpdir, delete=False)
            with tempfile.NamedTemporaryFile(
                **args
            ) as fileA, tempfile.NamedTemporaryFile(**args) as fileB:
                print(DUMMY_DDB_FILE, file=fileA, flush=True)
                print(
                    f"""
from {Path(fileA.name).stem} import device_db

device_db["new_core_alias"] = "core"
""",
                    file=fileB,
                    flush=True,
                )

                ddb = DeviceDB(fileB.name)
                self.assertEqual(
                    ddb.get("new_core_alias", resolve_alias=True),
                    DeviceDB(fileA.name).get("core"),
                )


class TestDeviceDB(unittest.TestCase):
    def setUp(self):
        self.ddb_file = tempfile.NamedTemporaryFile(
            mode="w+", suffix=".py", delete=False
        )
        print(DUMMY_DDB_FILE, file=self.ddb_file, flush=True)

        self.ddb = DeviceDB(self.ddb_file.name)

    def tearDown(self):
        self.ddb_file.close()
        os.unlink(self.ddb_file.name)

    def test_get(self):
        core = self.ddb.get("core")
        self.assertEqual(core["class"], "Core")

    def test_get_alias(self):
        with self.assertRaises(TypeError):  # str indexing on str
            self.ddb.get("core_alias")["class"]

        self.assertEqual(
            self.ddb.get("core_alias", resolve_alias=True), self.ddb.get("core")
        )

    def test_get_unresolved_alias(self):
        with self.assertRaisesRegex(KeyError, "dummy"):
            self.ddb.get("unresolved_alias", resolve_alias=True)

    def test_update(self):
        with self.assertRaises(KeyError):
            self.ddb.get("core_log")

        update = """
device_db["core_log"] = {
    "type": "controller",
    "host": "::1",
    "port": 1068,
    "command": "aqctl_corelog -p {port} --bind {bind} ::1",
}"""

        print(update, file=self.ddb_file, flush=True)
        self.ddb.scan()

        self.assertEqual(self.ddb.get("core_log")["type"], "controller")

    def test_get_ddb(self):
        ddb = self.ddb.get_device_db()
        raw = file_import(self.ddb_file.name).device_db

        self.assertEqual(ddb, raw)
