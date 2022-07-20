import unittest
import logging
import asyncio
import sys
from time import time, sleep

from artiq.experiment import *
from artiq.master.scheduler import Scheduler
from sipyco.sync_struct import process_mod

basic_flow = ["pending", "preparing", "prepare_done", "running",
              "run_done", "analyzing", "deleting"]

flush_flow = ["pending", "flushing", "preparing", "prepare_done",
              "running", "run_done", "analyzing", "deleting"]

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
    def __init__(self, end_condition="deleting"):
        self.experiments = {}
        self.last_status = {}
        self.exp_flow = {}
        self.status_records = {
            "pending": [],
            "preparing": [],
            "prepare_done": [],
            "running": [],
            "run_done": [],
            "analyzing": [],
            "deleting": [],
            "paused": [],
            "flushing": []
        }
        self.finished = False
        self.end_condition = end_condition
        self.flags = {"arrive": {}, "leave": {}}

    def record(self):
        for key, value in self.experiments.items():
            if key not in self.last_status.keys():
                self.last_status[key] = ""
                self.exp_flow[key] = []
            current_status = self.experiments[key]["status"]
            if current_status != self.last_status[key]:
                self.last_status[key] = current_status
                if self.exp_flow[key]:
                    self.exp_flow[key][-1]["out_time"] = time()
                self.exp_flow[key].append({
                    "status": current_status,
                    "in_time": time(),
                    "out_time": "never"
                })
                self.status_records[current_status].append(key)

                if key in self.flags["arrive"].keys():
                    if current_status in self.flags["arrive"][key].keys():
                        self.flags["arrive"][key][current_status].set()
                        self.remove_flag(key, "arrive", current_status)
                if key in self.flags["leave"].keys():
                    if self.last_status[key] in self.flags["leave"][key].keys():
                        self.flags["leave"][key][current_status].set()
                        self.remove_flag(key, "leave", current_status)

                if current_status == self.end_condition:
                    self.finished = True
                return

    def get_in_time(self, rid, status):
        for step in self.exp_flow[rid]:
            if step["status"] == status:
                return step["in_time"]

    def get_out_time(self, rid, status):
        for step in self.exp_flow[rid]:
            if step["status"] == status:
                return step["out_time"]

    def get_exp_order(self, status):
        return self.status_records[status]

    def get_status_order(self, rid):
        return [step["status"] for step in self.exp_flow[rid]]

    async def wait_until(self, rid, condition, status):
        # condition : "arrive", "leave"
        if self.last_status[rid] == status:
            return
        if rid not in self.flags[condition] or\
            status not in self.flags[condition][rid]:
            self.add_flag(rid, condition, status)
        await self.flags[condition][rid][status].wait()

    def add_flag(self, rid, condition, status):
        if rid not in self.flags[condition]:
            self.flags[condition][rid] = {}
        self.flags[condition][rid][status] = asyncio.Event()

    def remove_flag(self, rid, condition, status):
        del self.flags[condition][rid][status]
        if not self.flags[condition][rid]:
            del self.flags[condition][rid]

class SchedulerCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_steps(self):
        loop = self.loop
        scheduler = Scheduler(_RIDCounter(0), dict(), None, None)
        expid = _get_expid("EmptyExperiment")
        monitor = SchedulerMonitor()

        def notify(mod):
            process_mod(monitor.experiments, mod)
            monitor.record()
        scheduler.notifier.publish = notify

        scheduler.start()

        # Verify that a timed experiment far in the future does not
        # get run, even if it has high priority.
        late = time() + 100000
        scheduler.submit("main", expid, 99, late, False)

        # This one (RID 1) gets run instead.
        scheduler.submit("main", expid, 0, None, False)

        loop.run_until_complete(monitor.wait_until(1, "arrive", "deleting"))
        self.assertEqual(monitor.get_status_order(1), basic_flow)
        self.assertEqual(monitor.last_status[0], "pending")
        scheduler.notifier.publish = None
        loop.run_until_complete(scheduler.stop())

    def test_pending_priority(self):
        """Check due dates take precedence over priorities when waiting to
        prepare."""
        loop = self.loop
        handlers = {}
        scheduler = Scheduler(_RIDCounter(0), handlers, None, None)
        handlers["scheduler_check_pause"] = scheduler.check_pause

        expid_empty = _get_expid("EmptyExperiment")

        expid_bg = _get_expid("CheckPauseBackgroundExperiment")
        # Suppress the SystemExit backtrace when worker process is killed.
        expid_bg["log_level"] = logging.CRITICAL

        high_priority = 3
        middle_priority = 2
        low_priority = 1
        late = time() + 100000
        early = time() + 1

        monitor = SchedulerMonitor()

        def notify(mod):
            process_mod(monitor.experiments, mod)
            monitor.record()

        scheduler.notifier.publish = notify

        scheduler.start()

        scheduler.submit("main", expid_bg, low_priority)
        scheduler.submit("main", expid_empty, high_priority, late)
        scheduler.submit("main", expid_empty, middle_priority, early)

        loop.run_until_complete(monitor.wait_until(2, "arrive", "deleting"))
        scheduler.notifier.publish = None
        loop.run_until_complete(scheduler.stop())

        # Assert
        self.assertEqual(monitor.get_exp_order("preparing"), [0, 2])
        self.assertEqual(monitor.get_out_time(1, "pending"), "never",
                         "RID 1 has left pending")

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
        scheduler = Scheduler(_RIDCounter(0), handlers, None, None)

        expid_bg = _get_expid("BackgroundExperiment")
        expid = _get_expid("EmptyExperiment")

        monitor = SchedulerMonitor()
        def notify(mod):
            process_mod(monitor.experiments, mod)
            monitor.record()
        scheduler.notifier.publish = notify

        scheduler.start()
        scheduler.submit("main", expid_bg, -99, None, False)
        loop.run_until_complete(monitor.wait_until(0, "arrive", "running"))
        self.assertFalse(scheduler.check_pause(0))
        scheduler.submit("main", expid, 0, None, False)
        self.assertFalse(scheduler.check_pause(0))
        loop.run_until_complete(monitor.wait_until(1, "arrive", "prepare_done"))
        self.assertTrue(scheduler.check_pause(0))
        loop.run_until_complete(monitor.wait_until(1, "arrive", "deleting"))
        self.assertFalse(scheduler.check_pause(0))

        self.assertFalse(termination_ok)
        scheduler.request_termination(0)
        self.assertTrue(scheduler.check_pause(0))
        loop.run_until_complete(monitor.wait_until(0, "arrive", "deleting"))
        self.assertTrue(termination_ok)
        self.assertEqual(monitor.get_status_order(1), basic_flow)

        loop.run_until_complete(scheduler.stop())

    def test_close_with_active_runs(self):
        """Check scheduler exits with experiments still running"""
        loop = self.loop

        scheduler = Scheduler(_RIDCounter(0), {}, None, None)

        expid_bg = _get_expid("BackgroundExperiment")
        # Suppress the SystemExit backtrace when worker process is killed.
        expid_bg["log_level"] = logging.CRITICAL
        monitor = SchedulerMonitor()
        expid = _get_expid("EmptyExperiment")

        def notify(mod):
            process_mod(monitor.experiments, mod)
            monitor.record()

        scheduler.notifier.publish = notify

        scheduler.start()
        scheduler.submit("main", expid_bg, -99, None, False)
        loop.run_until_complete(monitor.wait_until(0, "arrive", "running"))

        scheduler.submit("main", expid, 0, None, False)
        loop.run_until_complete(monitor.wait_until(1, "arrive", "prepare_done"))

        # At this point, (at least) BackgroundExperiment is still running; make
        # sure we can stop the scheduler without hanging.
        loop.run_until_complete(scheduler.stop())

    def test_flush(self):
        loop = self.loop
        handlers = {}
        scheduler = Scheduler(_RIDCounter(0), handlers, None, None)
        handlers["scheduler_check_pause"] = scheduler.check_pause
        expid = _get_expid("EmptyExperiment")
        expid_bg = _get_expid("CheckPauseBackgroundExperiment")
        expid_bg["log_level"] = logging.CRITICAL
        monitor = SchedulerMonitor()

        def notify(mod):
            process_mod(monitor.experiments, mod)
            monitor.record()

        scheduler.notifier.publish = notify

        scheduler.start()
        # Flush with same priority
        scheduler.submit("main", expid, 0, None, False)
        scheduler.submit("main", expid, 0, None, True)
        loop.run_until_complete(monitor.wait_until(1, "arrive", "preparing"))
        self.assertEqual(monitor.last_status[0], "deleting")
        loop.run_until_complete(monitor.wait_until(1, "arrive", "deleting"))
        self.assertEqual(monitor.get_status_order(0), basic_flow)
        self.assertEqual(monitor.get_status_order(1), flush_flow)

        # Flush with higher priority
        scheduler.submit("main", expid_bg, 0, None, False)
        # Make sure RID 2 go into preparing stage first
        loop.run_until_complete(monitor.wait_until(2, "arrive", "preparing"))
        scheduler.submit("main", expid, 1, None, True)
        loop.run_until_complete(monitor.wait_until(3, "arrive", "deleting"))
        self.assertEqual(monitor.last_status[2], "running")
        self.assertEqual(monitor.get_status_order(3), flush_flow)

        loop.run_until_complete(scheduler.stop())

    def tearDown(self):
        self.loop.close()
