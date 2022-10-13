import unittest
import logging
import asyncio
import sys
from time import time, sleep

from artiq.experiment import *
from artiq.master.scheduler import Scheduler
from sipyco.sync_struct import process_mod


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
                             broadcast=True, archive=False)


class CheckPauseBackgroundExperiment(EnvExperiment):
    def build(self):
        self.setattr_device("scheduler")

    def run(self):
        while True:
            while not self.scheduler.check_pause():
                sleep(0.2)
            self.scheduler.pause()


def _get_expid(name):
    return {
        "log_level": logging.WARNING,
        "file": sys.modules[__name__].__file__,
        "class_name": name,
        "arguments": dict()
    }


def _make_status_events(rids):
    return {
        rid: {
            key: asyncio.Event()
            for key in (
                "pending", "preparing", "prepare_done",
                "running", "run_done", "analyzing",
                "deleting", "paused", "flushing"
            )
        } for rid in rids
    }


class _RIDCounter:
    def __init__(self, next_rid):
        self._next_rid = next_rid

    def get(self):
        rid = self._next_rid
        self._next_rid += 1
        return rid


class SchedulerCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.experiments = {}
        self.status_events = {}
        self.handlers = {}
        self.scheduler = Scheduler(_RIDCounter(0), self.handlers, None, None)
        self.scheduler.notifier.publish = self._notify

    def configure(self, rids):
        self.status_events = _make_status_events(rids)

    def _notify(self, mod):
        process_mod(self.experiments, mod)
        for rid, events in self.status_events.items():
            if (mod["action"] == "setitem" and
                    mod["key"] == rid and
                    mod["value"]["status"] == "pending"):
                events["pending"].set()
            if (mod["action"] == "setitem" and
                    mod["key"] == "status" and
                    mod["path"] == [rid] and
                    mod["value"] in events):
                events[mod["value"]].set()

    def assertStatusEqual(self, rid, status):
        actual = self.experiments[rid]["status"]
        if status != actual:
            raise AssertionError(f"RID {rid} should have status {status}, "
                                 f"got {actual}")

    def assertArriveStatus(self, rid, status, timeout=5):
        try:
            self.loop.run_until_complete(
                asyncio.wait_for(
                    self.status_events[rid][status].wait(), timeout))
        except asyncio.TimeoutError:
            raise AssertionError(f"Rid {rid} did not arrive "
                                 f"{status} within {timeout}s")

    def assertFirstArriveStatus(self, first_rid, rids, status):
        futures = {
            rid: asyncio.ensure_future(self.status_events[rid][status].wait())
            for rid in rids
        }
        done, pending = self.loop.run_until_complete(asyncio.wait(
            futures.values(),
            return_when=asyncio.FIRST_COMPLETED))
        for task in pending:
            task.cancel()
        if futures[first_rid] not in done:
            raise AssertionError(
                f"RID {first_rid} did not arrive {status} first"
            )

    def test_steps(self):
        self.configure([0, 1])
        expid = _get_expid("EmptyExperiment")

        self.scheduler.start()

        # Verify that a timed experiment far in the future does not
        # get run, even if it has high priority.
        late = time() + 100000
        self.scheduler.submit("main", expid, 99, late, False)

        # This one (RID 1) gets run instead.
        self.scheduler.submit("main", expid, 0, None, False)

        self.assertArriveStatus(1, "deleting")
        self.assertStatusEqual(0, "pending")

        self.loop.run_until_complete(self.scheduler.stop())

    def test_pending_priority(self):
        """Check due dates take precedence over priorities when waiting to
        prepare."""
        self.configure([0, 1, 2])
        self.handlers["scheduler_check_pause"] = self.scheduler.check_pause

        expid_empty = _get_expid("EmptyExperiment")

        expid_bg = _get_expid("CheckPauseBackgroundExperiment")
        # Suppress the SystemExit backtrace when worker process is killed.
        expid_bg["log_level"] = logging.CRITICAL

        high_priority = 3
        middle_priority = 2
        low_priority = 1
        late = time() + 100000
        early = time() + 1

        self.scheduler.start()
        self.scheduler.submit("main", expid_bg, low_priority)
        self.scheduler.submit("main", expid_empty, high_priority, late)
        self.scheduler.submit("main", expid_empty, middle_priority, early)

        self.assertArriveStatus(0, "paused")
        self.assertFirstArriveStatus(2, [1, 2], "running")

        self.loop.run_until_complete(self.scheduler.stop())

    def test_pause(self):
        self.configure([0, 1])
        termination_ok = False

        def check_termination(mod):
            nonlocal termination_ok
            self.assertEqual(
                mod,
                {"action": "setitem", "key": "termination_ok",
                 "value": (False, True), "path": []})
            termination_ok = True
        self.handlers["update_dataset"] = check_termination

        expid_bg = _get_expid("BackgroundExperiment")
        expid = _get_expid("EmptyExperiment")

        self.scheduler.start()
        # check_pause is True when rid with higher priority is prepare_done
        self.scheduler.submit("main", expid_bg, -99, None, False)
        self.assertArriveStatus(0, "running")
        self.assertFalse(self.scheduler.check_pause(0))
        self.scheduler.submit("main", expid, 0, None, False)
        self.assertFalse(self.scheduler.check_pause(0))
        self.assertArriveStatus(1, "prepare_done")
        self.assertTrue(self.scheduler.check_pause(0))
        self.assertArriveStatus(1, "deleting")
        self.assertFalse(self.scheduler.check_pause(0))

        # check_pause is True when request_termination is called
        self.assertFalse(termination_ok)
        self.assertFalse(self.scheduler.check_pause(0))
        self.scheduler.request_termination(0)
        self.assertTrue(self.scheduler.check_pause(0))
        self.assertArriveStatus(0, "deleting")
        self.assertTrue(termination_ok)

        self.loop.run_until_complete(self.scheduler.stop())

    def test_close_with_active_runs(self):
        """Check scheduler exits with experiments still running"""
        self.configure([0, 1])
        expid_bg = _get_expid("BackgroundExperiment")
        # Suppress the SystemExit backtrace when worker process is killed.
        expid_bg["log_level"] = logging.CRITICAL
        expid = _get_expid("EmptyExperiment")

        self.scheduler.start()
        self.scheduler.submit("main", expid_bg, -99, None, False)
        self.assertArriveStatus(0, "running")

        self.scheduler.submit("main", expid, 0, None, False)
        self.assertArriveStatus(1, "prepare_done")

        # At this point, (at least) BackgroundExperiment is still running; make
        # sure we can stop the scheduler without hanging.
        self.loop.run_until_complete(self.scheduler.stop())

    def test_flush(self):
        self.configure([0, 1])
        expid = _get_expid("EmptyExperiment")

        self.scheduler.start()
        self.scheduler.submit("main", expid, 0, None, False)
        self.assertArriveStatus(0, "preparing")
        self.scheduler.submit("main", expid, 1, None, True)
        self.assertArriveStatus(1, "flushing")
        self.loop.run_until_complete(self.scheduler.stop())

    def tearDown(self):
        self.loop.close()
