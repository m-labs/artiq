import unittest
import logging
import asyncio
import sys
import os
from time import sleep

from artiq.experiment import *
from artiq.master.worker import *


class SimpleExperiment(EnvExperiment):
    def build(self):
        pass

    def run(self):
        pass


class ExceptionTermination(EnvExperiment):
    def build(self):
        pass

    def run(self):
        raise TypeError


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


async def _call_worker(worker, expid):
    try:
        await worker.build(0, "main", None, expid, 0)
        await worker.prepare()
        await worker.run()
        await worker.analyze()
    finally:
        await worker.close()


def _run_experiment(class_name):
    expid = {
        "log_level": logging.WARNING,
        "file": sys.modules[__name__].__file__,
        "class_name": class_name,
        "arguments": dict()
    }
    loop = asyncio.get_event_loop()
    worker = Worker({})
    loop.run_until_complete(_call_worker(worker, expid))


class WorkerCase(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_simple_run(self):
        _run_experiment("SimpleExperiment")

    def test_exception(self):
        with self.assertLogs() as logs:
            with self.assertRaises(WorkerInternalException):
                _run_experiment("ExceptionTermination")
            self.assertGreater(len(logs.records), 0)
            self.assertIn("Terminating with exception (TypeError)",
                          logs.output[-1])

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
