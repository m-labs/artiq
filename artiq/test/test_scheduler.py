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


class _RIDCounter:
    def __init__(self, next_rid):
        self._next_rid = next_rid

    def get(self):
        rid = self._next_rid
        self._next_rid += 1
        return rid


class SchedulerMonitor:
    flow_map = {   # current status -> possible move
            "": {"pending"},
            "pending": {"preparing", "flushing", "deleting"},
            "preparing": {"prepare_done", "deleting"},
            "prepare_done": {"running", "deleting"},
            "running": {"run_done", "paused", "deleting"},
            "run_done": {"analyzing", "deleting"},
            "analyzing": {"deleting"},
            "deleting": {},
            "paused": {"running"},
            "flushing": {"preparing"}
        }

    def __init__(self, test):
        self.test = test
        self.experiments = {}
        self.last_status = {}
        self.flags = {"arrive": {}, "leave": {}}

    def record(self, mod):
        process_mod(self.experiments, mod)
        for rid, exp_info in self.experiments.items():
            if rid not in self.last_status.keys():
                self.last_status[rid] = ""
            if exp_info["status"] != self.last_status[rid]:
                self.test.assertIn(exp_info["status"],
                                   self.flow_map[self.last_status[rid]])

                if rid in self.flags["arrive"].keys():
                    if exp_info["status"] in self.flags["arrive"][rid].keys():
                        self.flags["arrive"][rid][exp_info["status"]].set()
                if rid in self.flags["leave"].keys():
                    if self.last_status[rid] in self.flags["leave"][rid].keys():
                        self.flags["leave"][rid][self.last_status[rid]].set()

                self.last_status[rid] = exp_info["status"]
                return

    async def wait_until(self, rid, condition, status):
        # condition : "arrive", "leave"
        if self.last_status[rid] == status and condition == "arrive":
            return
        if rid not in self.flags[condition] or\
                status not in self.flags[condition][rid]:
            self.add_flag(rid, condition, status)
        await self.flags[condition][rid][status].wait()
        self.remove_flag(rid, condition, status)
        return rid

    def add_flag(self, rid, condition, status):
        if rid not in self.flags[condition]:
            self.flags[condition][rid] = {}
        self.flags[condition][rid][status] = asyncio.Event()

    def remove_flag(self, rid, condition, status):
        if rid in self.flags[condition].keys():
            if status in self.flags[condition][rid].keys():
                del self.flags[condition][rid][status]
            if not self.flags[condition][rid]:
                del self.flags[condition][rid]


class SchedulerCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.handlers = {}
        self.scheduler = Scheduler(_RIDCounter(0), self.handlers, None, None)
        self.monitor = SchedulerMonitor(self)
        self.scheduler.notifier.publish = self.monitor.record
        self.scheduler.start()

    def test_steps(self):
        expid = _get_expid("EmptyExperiment")

        # Verify that a timed experiment far in the future does not
        # get run, even if it has high priority.
        late = time() + 100000
        self.scheduler.submit("main", expid, 99, late, False)

        # This one (RID 1) gets run instead.
        self.scheduler.submit("main", expid, 0, None, False)

        self.loop.run_until_complete(self.monitor.wait_until(1, "arrive", "deleting"))
        self.assertEqual(self.monitor.last_status[0], "pending")

    def test_pending_priority(self):
        """Check due dates take precedence over priorities when waiting to
        prepare."""
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

        self.scheduler.submit("main", expid_bg, low_priority)
        self.scheduler.submit("main", expid_empty, high_priority, late)
        self.scheduler.submit("main", expid_empty, middle_priority, early)

        wait_RID1_leave = self.loop.create_task(
            self.monitor.wait_until(1, "leave", "pending"))
        wait_RID2_leave = self.loop.create_task(
            self.monitor.wait_until(2, "leave", "pending"))
        done, pending = self.loop.run_until_complete(asyncio.wait(
            [wait_RID1_leave, wait_RID2_leave],
            return_when=asyncio.FIRST_COMPLETED))
        self.assertIn(wait_RID2_leave, done)
        for task in pending:
            task.cancel()

        self.loop.run_until_complete(self.monitor.wait_until(2, "arrive", "deleting"))

    def test_pause(self):
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

        # check_pause is True when rid with higher priority is prepare_done
        self.scheduler.submit("main", expid_bg, -99, None, False)
        self.loop.run_until_complete(self.monitor.wait_until(0, "arrive", "running"))
        self.assertFalse(self.scheduler.check_pause(0))
        self.scheduler.submit("main", expid, 0, None, False)
        self.assertFalse(self.scheduler.check_pause(0))
        self.loop.run_until_complete(self.monitor.wait_until(1, "arrive", "prepare_done"))
        self.assertTrue(self.scheduler.check_pause(0))
        self.loop.run_until_complete(self.monitor.wait_until(1, "arrive", "deleting"))
        self.assertFalse(self.scheduler.check_pause(0))

        # check_pause is True when request_termination is called
        self.assertFalse(termination_ok)
        self.assertFalse(self.scheduler.check_pause(0))
        self.scheduler.request_termination(0)
        self.assertTrue(self.scheduler.check_pause(0))
        self.loop.run_until_complete(self.monitor.wait_until(0, "arrive", "deleting"))
        self.assertTrue(termination_ok)

    def test_close_with_active_runs(self):
        """Check scheduler exits with experiments still running"""
        expid_bg = _get_expid("BackgroundExperiment")
        # Suppress the SystemExit backtrace when worker process is killed.
        expid_bg["log_level"] = logging.CRITICAL
        expid = _get_expid("EmptyExperiment")

        self.scheduler.submit("main", expid_bg, -99, None, False)
        self.loop.run_until_complete(self.monitor.wait_until(0, "arrive", "running"))

        self.scheduler.submit("main", expid, 0, None, False)
        self.loop.run_until_complete(self.monitor.wait_until(1, "arrive", "prepare_done"))

        # At this point, (at least) BackgroundExperiment is still running; make
        # sure we can stop the scheduler without hanging.

    def test_flush(self):
        self.handlers["scheduler_check_pause"] = self.scheduler.check_pause
        expid = _get_expid("EmptyExperiment")
        expid_bg = _get_expid("CheckPauseBackgroundExperiment")
        expid_bg["log_level"] = logging.CRITICAL

        # Flush with same priority
        self.scheduler.submit("main", expid, 0, None, False)
        self.scheduler.submit("main", expid, 0, None, True)
        self.loop.run_until_complete(self.monitor.wait_until(1, "arrive", "preparing"))
        self.assertEqual(self.monitor.last_status[0], "deleting")
        self.loop.run_until_complete(self.monitor.wait_until(1, "arrive", "deleting"))

        # Flush with higher priority
        self.scheduler.submit("main", expid_bg, 0, None, False)
        # Make sure RID 2 go into preparing stage first
        self.loop.run_until_complete(self.monitor.wait_until(2, "arrive", "preparing"))
        self.scheduler.submit("main", expid, 1, None, True)
        self.loop.run_until_complete(self.monitor.wait_until(3, "arrive", "deleting"))
        self.assertEqual(self.monitor.last_status[2], "running")

    def tearDown(self):
        self.loop.run_until_complete(self.scheduler.stop())
        self.loop.close()
