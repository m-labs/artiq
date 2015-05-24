import unittest
import asyncio
import sys
from time import sleep

from artiq import *
from artiq.master.worker import *


class WatchdogNoTimeout(Experiment, AutoDB):
    def run(self):
        for i in range(10):
            with watchdog(0.5*s):
                sleep(0.1)


class WatchdogTimeout(Experiment, AutoDB):
    def run(self):
        with watchdog(0.1*s):
            sleep(100.0)


class WatchdogTimeoutInBuild(Experiment, AutoDB):
    def build(self):
        with watchdog(0.1*s):
            sleep(100.0)

    def run(self):
        pass


@asyncio.coroutine
def _call_worker(worker, expid):
    yield from worker.prepare(0, "main", expid, 0)
    try:
        yield from worker.run()
        yield from worker.analyze()
    finally:
        yield from worker.close()


def _run_experiment(experiment):
    expid = {
        "file": sys.modules[__name__].__file__,
        "experiment": experiment,
        "arguments": dict()
    }
    handlers = {
        "init_rt_results": lambda description: None
    }

    worker = Worker(handlers)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_call_worker(worker, expid))


class WatchdogCase(unittest.TestCase):
    def test_watchdog_no_timeout(self):
       _run_experiment("WatchdogNoTimeout")

    def test_watchdog_timeout(self):
        with self.assertRaises(WorkerWatchdogTimeout):
            _run_experiment("WatchdogTimeout")

    def test_watchdog_timeout_in_build(self):
        with self.assertRaises(WorkerWatchdogTimeout):
            _run_experiment("WatchdogTimeoutInBuild")
