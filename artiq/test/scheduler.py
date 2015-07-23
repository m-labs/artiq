import unittest
import asyncio
import sys
from time import time, sleep

from artiq import *
from artiq.master.scheduler import Scheduler


class EmptyExperiment(EnvExperiment):
    def build(self):
        pass

    def run(self):
        pass


class BackgroundExperiment(EnvExperiment):
    def build(self):
        self.attr_device("scheduler")

    def run(self):
        while True:
            self.scheduler.pause()
            sleep(0.2)


def _get_expid(name):
    return {
        "file": sys.modules[__name__].__file__,
        "class_name": name,
        "arguments": dict()
    }


def _get_basic_steps(rid, expid, priority=0, flush=False):
    return [
        {"action": "setitem", "key": rid, "value": 
            {"pipeline": "main", "status": "pending", "priority": priority,
             "expid": expid, "due_date": None, "flush": flush},
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
        {"action": "setitem", "key": "status", "value": "analyze_done",
            "path": [rid]},
        {"action": "delitem", "key": rid, "path": []}
    ]


_handlers = {
    "init_rt_results": lambda description: None
}


class SchedulerCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_steps(self):
        loop = self.loop
        scheduler = Scheduler(0, _handlers)
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
                 "expid": expid, "due_date": late, "flush": False},
             "path": []})
        scheduler.submit("main", expid, 99, late, False)

        # This one (RID 1) gets run instead.
        scheduler.submit("main", expid, 0, None, False)

        loop.run_until_complete(done.wait())
        scheduler.notifier.publish = None
        loop.run_until_complete(scheduler.stop())

    def test_pause(self):
        loop = self.loop
        scheduler = Scheduler(0, _handlers)
        expid_bg = _get_expid("BackgroundExperiment")
        expid = _get_expid("EmptyExperiment")

        expect = _get_basic_steps(1, expid)
        background_running = asyncio.Event()
        done = asyncio.Event()
        expect_idx = 0
        def notify(mod):
            nonlocal expect_idx
            if mod == {"path": [0],
                       "value": "running",
                       "key": "status",
                       "action": "setitem"}:
                background_running.set()
            if mod["path"] == [1] or (mod["path"] == [] and mod["key"] == 1):
                self.assertEqual(mod, expect[expect_idx])
                expect_idx += 1
                if expect_idx >= len(expect):
                    done.set()
        scheduler.notifier.publish = notify

        scheduler.start()
        scheduler.submit("main", expid_bg, -99, None, False)
        loop.run_until_complete(background_running.wait())
        scheduler.submit("main", expid, 0, None, False)
        loop.run_until_complete(done.wait())
        loop.run_until_complete(scheduler.stop())

    def test_flush(self):
        loop = self.loop
        scheduler = Scheduler(0, _handlers)
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
