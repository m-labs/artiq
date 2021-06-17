"""Test internal dataset representation (persistence, applets)"""
import unittest
import tempfile

from artiq.master.databases import DatasetDB
from sipyco import pyon

KEY1 = "key1"
KEY2 = "key2"
KEY3 = "key3"
DATA = list(range(10))
COMP = "gzip"


class TestDatasetDB(unittest.TestCase):
    def setUp(self):
        # empty dataset persistance file
        self.persist_file = tempfile.NamedTemporaryFile(mode="w+")
        print("{}", file=self.persist_file, flush=True)

        self.ddb = DatasetDB(self.persist_file.name)

        self.ddb.set(KEY1, DATA, persist=True)
        self.ddb.set(KEY2, DATA, persist=True, hdf5_options=dict(compression=COMP))
        self.ddb.set(KEY3, DATA, hdf5_options=dict(shuffle=True))

        self.save_ddb_to_disk()

    def save_ddb_to_disk(self):
        self.ddb.save()
        self.persist_file.flush()

    def load_ddb_from_disk(self):
        return pyon.load_file(self.persist_file.name)

    def test_persist_format(self):
        data = pyon.load_file(self.persist_file.name)

        for key in [KEY1, KEY2]:
            self.assertTrue(data[key]["persist"])
            self.assertEqual(data[key]["value"], DATA)

        self.assertEqual(data[KEY2]["hdf5_options"]["compression"], COMP)
        self.assertEqual(data[KEY1]["hdf5_options"], dict())

    def test_only_persist_marked_datasets(self):
        data = self.load_ddb_from_disk()

        with self.assertRaises(KeyError):
            data[KEY3]

    def test_memory_format(self):
        ds = self.ddb.get(KEY2)
        self.assertTrue(ds["persist"])
        self.assertEqual(ds["value"], DATA)
        self.assertEqual(ds["hdf5_options"]["compression"], COMP)

        ds = self.ddb.get(KEY3)
        self.assertFalse(ds["persist"])
        self.assertEqual(ds["value"], DATA)
        self.assertTrue(ds["hdf5_options"]["shuffle"])

    def test_delete(self):
        self.ddb.delete(KEY1)
        self.save_ddb_to_disk()

        data = self.load_ddb_from_disk()

        with self.assertRaises(KeyError):
            data[KEY1]

        self.assertTrue(data[KEY2]["persist"])

    def test_update(self):
        self.assertFalse(self.ddb.get(KEY3)["persist"])

        mod = {
            "action": "setitem",
            "path": [KEY3],
            "key": "persist",
            "value": True,
        }

        self.ddb.update(mod)
        self.assertTrue(self.ddb.get(KEY3)["persist"])

    def test_update_hdf5_options(self):
        with self.assertRaises(KeyError):
            self.ddb.get(KEY1)["hdf5_options"]["shuffle"]

        mod = {
            "action": "setitem",
            "path": [KEY1, "hdf5_options"],
            "key": "shuffle",
            "value": False,
        }

        self.ddb.update(mod)
        self.assertFalse(self.ddb.get(KEY1)["hdf5_options"]["shuffle"])

    def test_reset_copies_persist(self):
        self.assertTrue(self.ddb.get(KEY1)["persist"])
        self.ddb.set(KEY1, DATA)
        self.assertTrue(self.ddb.get(KEY1)["persist"])

        self.assertFalse(self.ddb.get(KEY3)["persist"])
        self.ddb.set(KEY3, DATA)
        self.assertFalse(self.ddb.get(KEY3)["persist"])

        self.ddb.set(KEY3, DATA, persist=True)
        self.assertTrue(self.ddb.get(KEY3)["persist"])
