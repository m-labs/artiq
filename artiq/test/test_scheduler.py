import unittest
import logging
import asyncio
import sys
import os
from time import time, sleep

from artiq.experiment import *
from artiq.master.scheduler import Scheduler


class EmptyExperiment(EnvExperiment):
    def build(self):
        pass

    def run(self):
        pass


class BackgroundExperiment(EnvExperiment):
    def build(self):
        self.setattr_device("scheduler")

    def run(self):
        try:
            while True:
                self.scheduler.pause()
                sleep(0.2)
        except TerminationRequested:
            self.set_dataset("termination_ok", True,
                             broadcast=True, save=False)


def _get_expid(name):
    return {
        "log_level": logging.WARNING,
        "file": sys.modules[__name__].__file__,
        "class_name": name,
        "arguments": dict()
    }


def _get_basic_steps(rid, expid, priority=0, flush=False):
    return [
        {"action": "setitem", "key": rid, "value":
            {"pipeline": "main", "status": "pending", "priority": priority,
             "expid": expid, "due_date": None, "flush": flush,
             "repo_msg": None},
            "path": []},
        {"action": "setitem", "key": "status", "value": "preparing",
            "path": [rid]},
        {"action": "setitem", "key": "status", "value": "prepare_done",
            "path": [rid]},
        {"action": "setitem", "key": "status", "value": "running",
            "path": [rid]},
        {"action": "setitem", "key": "status", "value": "run_done",
            "path": [rid]},
        {"action": "setitem", "key": "status", "value": "analyzing",
            "path": [rid]},
        {"action": "setitem", "key": "status", "value": "deleting",
            "path": [rid]},
        {"action": "delitem", "key": rid, "path": []}
    ]


class _RIDCounter:
    def __init__(self, next_rid):
        self._next_rid = next_rid

    def get(self):
        rid = self._next_rid
        self._next_rid += 1
        return rid


class SchedulerCase(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_steps(self):
        loop = self.loop
        scheduler = Scheduler(_RIDCounter(0), dict(), None)
        expid = _get_expid("EmptyExperiment")

        expect = _get_basic_steps(1, expid)
        done = asyncio.Event()
        expect_idx = 0
        def notify(mod):
            nonlocal expect_idx
            self.assertEqual(mod, expect[expect_idx])
            expect_idx += 1
            if expect_idx >= len(expect):
                done.set()
        scheduler.notifier.publish = notify

        scheduler.start()

        # Verify that a timed experiment far in the future does not
        # get run, even if it has high priority.
        late = time() + 100000
        expect.insert(0,
            {"action": "setitem", "key": 0, "value":
                {"pipeline": "main", "status": "pending", "priority": 99,
                 "expid": expid, "due_date": late, "flush": False,
                 "repo_msg": None},
             "path": []})
        scheduler.submit("main", expid, 99, late, False)

        # This one (RID 1) gets run instead.
        scheduler.submit("main", expid, 0, None, False)

        loop.run_until_complete(done.wait())
        scheduler.notifier.publish = None
        loop.run_until_complete(scheduler.stop())

    def test_pause(self):
        loop = self.loop

        termination_ok = False
        def check_termination(mod):
            nonlocal termination_ok
            self.assertEqual(
                mod,
                {"action": "setitem", "key": "termination_ok",
                 "value": (False, True), "path": []})
            termination_ok = True
        handlers = {
            "update_dataset": check_termination
        }
        scheduler = Scheduler(_RIDCounter(0), handlers, None)

        expid_bg = _get_expid("BackgroundExperiment")
        expid = _get_expid("EmptyExperiment")

        expect = _get_basic_steps(1, expid)
        background_running = asyncio.Event()
        empty_ready = asyncio.Event()
        empty_completed = asyncio.Event()
        background_completed = asyncio.Event()
        expect_idx = 0
        def notify(mod):
            nonlocal expect_idx
            if mod == {"path": [0],
                       "value": "running",
                       "key": "status",
                       "action": "setitem"}:
                background_running.set()
            if mod == {"path": [0],
                       "value": "deleting",
                       "key": "status",
                       "action": "setitem"}:
                background_completed.set()
            if mod == {"path": [1],
                       "value": "prepare_done",
                       "key": "status",
                       "action": "setitem"}:
                empty_ready.set()
            if mod["path"] == [1] or (mod["path"] == [] and mod["key"] == 1):
                self.assertEqual(mod, expect[expect_idx])
                expect_idx += 1
                if expect_idx >= len(expect):
                    empty_completed.set()
        scheduler.notifier.publish = notify

        scheduler.start()
        scheduler.submit("main", expid_bg, -99, None, False)
        loop.run_until_complete(background_running.wait())
        self.assertFalse(scheduler.check_pause(0))
        scheduler.submit("main", expid, 0, None, False)
        self.assertFalse(scheduler.check_pause(0))
        loop.run_until_complete(empty_ready.wait())
        self.assertTrue(scheduler.check_pause(0))
        loop.run_until_complete(empty_completed.wait())
        self.assertFalse(scheduler.check_pause(0))

        self.assertFalse(termination_ok)
        scheduler.request_termination(0)
        self.assertTrue(scheduler.check_pause(0))
        loop.run_until_complete(background_completed.wait())
        self.assertTrue(termination_ok)

        loop.run_until_complete(scheduler.stop())

    def test_close_with_active_runs(self):
        """Check scheduler exits with experiments still running"""
        loop = self.loop

        scheduler = Scheduler(_RIDCounter(0), {}, None)

        expid_bg = _get_expid("BackgroundExperiment")
        # Suppress the SystemExit backtrace when worker process is killed.
        expid_bg["log_level"] = logging.CRITICAL
        expid = _get_expid("EmptyExperiment")

        background_running = asyncio.Event()
        empty_ready = asyncio.Event()
        background_completed = asyncio.Event()
        def notify(mod):
            if mod == {"path": [0],
                       "value": "running",
                       "key": "status",
                       "action": "setitem"}:
                background_running.set()
            if mod == {"path": [0],
                       "value": "deleting",
                       "key": "status",
                       "action": "setitem"}:
                background_completed.set()
            if mod == {"path": [1],
                       "value": "prepare_done",
                       "key": "status",
                       "action": "setitem"}:
                empty_ready.set()
        scheduler.notifier.publish = notify

        scheduler.start()
        scheduler.submit("main", expid_bg, -99, None, False)
        loop.run_until_complete(background_running.wait())

        scheduler.submit("main", expid, 0, None, False)
        loop.run_until_complete(empty_ready.wait())

        # At this point, (at least) BackgroundExperiment is still running; make
        # sure we can stop the scheduler without hanging.
        loop.run_until_complete(scheduler.stop())

    def test_flush(self):
        loop = self.loop
        scheduler = Scheduler(_RIDCounter(0), dict(), None)
        expid = _get_expid("EmptyExperiment")

        expect = _get_basic_steps(1, expid, 1, True)
        expect.insert(1, {"key": "status",
                          "path": [1],
                          "value": "flushing",
                          "action": "setitem"})
        first_preparing = asyncio.Event()
        done = asyncio.Event()
        expect_idx = 0
        def notify(mod):
            nonlocal expect_idx
            if mod == {"path": [0],
                       "value": "preparing",
                       "key": "status",
                       "action": "setitem"}:
                first_preparing.set()
            if mod["path"] == [1] or (mod["path"] == [] and mod["key"] == 1):
                self.assertEqual(mod, expect[expect_idx])
                expect_idx += 1
                if expect_idx >= len(expect):
                    done.set()
        scheduler.notifier.publish = notify

        scheduler.start()
        scheduler.submit("main", expid, 0, None, False)
        loop.run_until_complete(first_preparing.wait())
        scheduler.submit("main", expid, 1, None, True)
        loop.run_until_complete(done.wait())
        loop.run_until_complete(scheduler.stop())

    def tearDown(self):
        self.loop.close()
