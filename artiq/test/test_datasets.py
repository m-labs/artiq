"""Tests for the (Env)Experiment-facing dataset interface."""

import copy
import unittest

from sipyco.sync_struct import process_mod

from artiq.experiment import EnvExperiment
from artiq.master.worker_db import DatasetManager


class MockDatasetDB:
    def __init__(self):
        self.data = dict()

    def get(self, key):
        return self.data[key][1]

    def update(self, mod):
        # Copy mod before applying to avoid sharing references to objects
        # between this and the DatasetManager, which would lead to mods being
        # applied twice.
        process_mod(self.data, copy.deepcopy(mod))

    def delete(self, key):
        del self.data[key]


class TestExperiment(EnvExperiment):
    def get(self, key):
        return self.get_dataset(key)

    def set(self, key, value, **kwargs):
        self.set_dataset(key, value, **kwargs)

    def append(self, key, value):
        self.append_to_dataset(key, value)


KEY = "foo"


class ExperimentDatasetCase(unittest.TestCase):
    def setUp(self):
        # Create an instance of TestExperiment locally in this process and a
        # mock dataset db to back it. When used from the master, the worker IPC
        # connection would marshal updates between dataset_mgr and dataset_db.
        self.dataset_db = MockDatasetDB()
        self.dataset_mgr = DatasetManager(self.dataset_db)
        self.exp = TestExperiment((None, self.dataset_mgr, None, None))

    def test_set_local(self):
        with self.assertRaises(KeyError):
            self.exp.get(KEY)

        for i in range(2):    
            self.exp.set(KEY, i)
            self.assertEqual(self.exp.get(KEY), i)
            with self.assertRaises(KeyError):
                self.dataset_db.get(KEY)

    def test_set_broadcast(self):
        with self.assertRaises(KeyError):
            self.exp.get(KEY)

        self.exp.set(KEY, 0, broadcast=True)
        self.assertEqual(self.exp.get(KEY), 0)
        self.assertEqual(self.dataset_db.get(KEY), 0)

        self.exp.set(KEY, 1, broadcast=False)
        self.assertEqual(self.exp.get(KEY), 1)
        with self.assertRaises(KeyError):
            self.dataset_db.get(KEY)

    def test_append_local(self):
        self.exp.set(KEY, [])
        self.exp.append(KEY, 0)
        self.assertEqual(self.exp.get(KEY), [0])
        self.exp.append(KEY, 1)
        self.assertEqual(self.exp.get(KEY), [0, 1])

    def test_append_broadcast(self):
        self.exp.set(KEY, [], broadcast=True)
        self.exp.append(KEY, 0)
        self.assertEqual(self.dataset_db.data[KEY][1], [0])
        self.exp.append(KEY, 1)
        self.assertEqual(self.dataset_db.data[KEY][1], [0, 1])

    def test_append_array(self):
        for broadcast in (True, False):
            self.exp.set(KEY, [], broadcast=broadcast)
            self.exp.append(KEY, [])
            self.exp.append(KEY, [])
            self.assertEqual(self.exp.get(KEY), [[], []])

    def test_append_scalar_fails(self):
        for broadcast in (True, False):
            with self.assertRaises(AttributeError):
                self.exp.set(KEY, 0, broadcast=broadcast)
                self.exp.append(KEY, 1)

    def test_append_nonexistent_fails(self):
        with self.assertRaises(KeyError):
            self.exp.append(KEY, 0)

