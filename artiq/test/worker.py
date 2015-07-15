import unittest
import asyncio
import sys
from time import sleep

from artiq import *
from artiq.master.worker import *


class WatchdogNoTimeout(EnvExperiment):
    def build(self):
        pass

    def run(self):
        for i in range(10):
            with watchdog(0.5*s):
                sleep(0.1)


class WatchdogTimeout(EnvExperiment):
    def build(self):
        pass

    def run(self):
        with watchdog(0.1*s):
            sleep(100.0)


class WatchdogTimeoutInBuild(EnvExperiment):
    def build(self):
        with watchdog(0.1*s):
            sleep(100.0)

    def run(self):
        pass


@asyncio.coroutine
def _call_worker(worker, expid):
    try:
        yield from worker.build(0, "main", expid, 0)
        yield from worker.prepare()
        yield from worker.run()
        yield from worker.analyze()
    finally:
        yield from worker.close()


def _run_experiment(class_name):
    expid = {
        "file": sys.modules[__name__].__file__,
        "class_name": class_name,
        "arguments": dict()
    }
    loop = asyncio.get_event_loop()
    worker = Worker()
    loop.run_until_complete(_call_worker(worker, expid))


class WatchdogCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_watchdog_no_timeout(self):
        _run_experiment("WatchdogNoTimeout")

    def test_watchdog_timeout(self):
        with self.assertRaises(WorkerWatchdogTimeout):
            _run_experiment("WatchdogTimeout")

    def test_watchdog_timeout_in_build(self):
        with self.assertRaises(WorkerWatchdogTimeout):
            _run_experiment("WatchdogTimeoutInBuild")

    def tearDown(self):
        self.loop.close()
