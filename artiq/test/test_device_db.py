"""Test device DB interface"""

import unittest
import tempfile

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

    "core-alias": "core",
    "unresolved-alias": "dummy",
}
"""


class TestInvalidDeviceDB(unittest.TestCase):
    def test_no_device_db_in_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".py") as f:
            print("", file=f, flush=True)

            with self.assertRaisesRegex(KeyError, "device_db"):
                DeviceDB(f.name)


class TestDeviceDB(unittest.TestCase):
    def setUp(self):
        self.ddb_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".py")
        print(DUMMY_DDB_FILE, file=self.ddb_file, flush=True)

        self.ddb = DeviceDB(self.ddb_file.name)

    def test_get(self):
        core = self.ddb.get("core")
        self.assertEqual(core["class"], "Core")

    def test_get_alias(self):
        with self.assertRaises(TypeError):  # str indexing on str
            self.ddb.get("core-alias")["class"]

        self.assertEqual(
            self.ddb.get("core-alias", resolve_alias=True), self.ddb.get("core")
        )

    def test_get_unresolved_alias(self):
        with self.assertRaisesRegex(KeyError, "dummy"):
            self.ddb.get("unresolved-alias", resolve_alias=True)

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
