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
            with watchdog(0.5 * s):
                sleep(0.1)


class WatchdogTimeout(EnvExperiment):
    def build(self):
        pass

    def run(self):
        with watchdog(0.1 * s):
            sleep(100.0)


class WatchdogTimeoutInBuild(EnvExperiment):
    def build(self):
        with watchdog(0.1 * s):
            sleep(100.0)

    def run(self):
        pass


class SendList(EnvExperiment):
    def build(self):
        self.setattr_argument(
            "array_length",
            NumberValue(default=10000, scale=1, ndecimals=0, step=1, type="int"),
        )

    def run(self):
        from random import random
        from timeit import timeit

        data = [random() for _ in range(self.array_length)]

        duration = timeit(
            lambda: self.set_dataset("test", data, broadcast=True), number=1
        )
        self.set_dataset("duration", duration, broadcast=True)

class SendArray(EnvExperiment):
    def build(self):
        self.setattr_argument(
            "array_length",
            NumberValue(default=10000, scale=1, ndecimals=0, step=1, type="int"),
        )

    def run(self):
        from random import random
        from timeit import timeit
        import numpy as np

        data = np.array([random() for _ in range(self.array_length)])

        duration = timeit(
            lambda: self.set_dataset("test", data, broadcast=True), number=1
        )
        self.set_dataset("duration", duration, broadcast=True)


async def _call_worker(worker, expid):
    try:
        await worker.build(0, "main", None, expid, 0)
        await worker.prepare()
        await worker.run()
        await worker.analyze()
    finally:
        await worker.close()


def _run_experiment(class_name, handlers={}, args={}):
    expid = {
        "log_level": logging.WARNING,
        "file": sys.modules[__name__].__file__,
        "class_name": class_name,
        "arguments": args,
    }
    loop = asyncio.get_event_loop()
    worker = Worker(handlers)
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
            self.assertIn("Terminating with exception (TypeError)", logs.output[-1])

    def test_watchdog_no_timeout(self):
        _run_experiment("WatchdogNoTimeout")

    def test_watchdog_timeout(self):
        with self.assertRaises(WorkerWatchdogTimeout):
            _run_experiment("WatchdogTimeout")

    def test_watchdog_timeout_in_build(self):
        with self.assertRaises(WorkerWatchdogTimeout):
            _run_experiment("WatchdogTimeoutInBuild")

    def test_data_transfer_speed(self):
        sizes = [1e3, 1e4, 1e5, 5e5, 1e6, 5e6]
        durations_lists = []

        def mock_update_dataset(*args, **kwargs):
            dataset_name = args[0]["key"]
            new_value = args[0]["value"][1]
            if dataset_name == "duration":
                durations_lists.append(new_value)

        for size in sizes:
            _run_experiment(
                "SendList",
                {"update_dataset": mock_update_dataset},
                {"array_length": size},
            )

        durations_arrays = []

        def mock_update_dataset(*args, **kwargs):
            dataset_name = args[0]["key"]
            new_value = args[0]["value"][1]
            if dataset_name == "duration":
                durations_arrays.append(new_value)
        
        for size in sizes:
            _run_experiment(
                "SendArray",
                {"update_dataset": mock_update_dataset},
                {"array_length": size},
            )

        for size, duration in zip(sizes, durations_lists):
            print("Writing %s elements as lists took %.2f ms" % (size, 1e3 * duration))
        for size, duration in zip(sizes, durations_arrays):
            print("Writing %s elements as arrays took %.2f ms" % (size, 1e3 * duration))

        for size, duration in zip(sizes, durations_lists):
            print("%s,%.2f" % (size, 1e3 * duration))
        for size, duration in zip(sizes, durations_arrays):
            print("%s,%.2f" % (size, 1e3 * duration))

    def tearDown(self):
        self.loop.close()
