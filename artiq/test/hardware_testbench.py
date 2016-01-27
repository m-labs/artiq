# Copyright (C) 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os
import sys
import unittest
import logging
import asyncio
import atexit

from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.worker_db import DeviceManager, DatasetManager
from artiq.coredevice.core import CompileError
from artiq.frontend.artiq_run import DummyScheduler
from artiq.devices.ctlmgr import Controllers


artiq_root = os.getenv("ARTIQ_ROOT")
logger = logging.getLogger(__name__)


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ControllerCase(unittest.TestCase):
    host_filter = "::1"
    timeout = 2

    def setUp(self):
        if os.name == "nt":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        atexit.register(self.loop.close)

        self.controllers = Controllers()
        self.controllers.host_filter = self.host_filter

        self.device_db = DeviceDB(os.path.join(artiq_root, "device_db.pyon"))
        self.device_mgr = DeviceManager(self.device_db)

    async def start(self, *names):
        for name in names:
            try:
                self.controllers[name] = self.device_db.get(name)
            except KeyError:
                raise unittest.SkipTest(
                    "controller `{}` not found".format(name))
        await self.controllers.queue.join()
        await asyncio.wait([asyncio.ensure_future(self.wait_for_ping(name))
                            for name in names])

    async def wait_for_ping(self, name, retries=5):
        t = self.timeout
        dt = t/retries
        while t > 0:
            try:
                ok = await asyncio.wait_for(
                    self.controllers.active[name].call("ping"), dt)
                if not ok:
                    raise ValueError("unexcepted ping() response from "
                                     "controller `{}`: `{}`".format(name, ok))
                return ok
            except asyncio.TimeoutError:
                t -= dt
            except (ConnectionAbortedError, ConnectionError,
                    ConnectionRefusedError, ConnectionResetError):
                await asyncio.sleep(dt)
                t -= dt
        raise asyncio.TimeoutError


def with_controllers(*names):
    def wrapper(func):
        def inner(self):
            try:
                for name in names:
                    setattr(self, name, self.device_mgr.get(name))
                func(self)
            finally:
                self.device_mgr.close_devices()

        def wrapped_test(self):
            try:
                self.loop.run_until_complete(self.start(*names))
                self.loop.run_until_complete(self.loop.run_in_executor(
                    None, inner, self))
            finally:
                self.loop.run_until_complete(self.controllers.shutdown())

        return wrapped_test
    return wrapper


@unittest.skipUnless(artiq_root, "no ARTIQ_ROOT")
class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self.device_db = DeviceDB(os.path.join(artiq_root, "device_db.pyon"))
        self.dataset_db = DatasetDB(
            os.path.join(artiq_root, "dataset_db.pyon"))
        self.device_mgr = DeviceManager(
            self.device_db, virtual_devices={"scheduler": DummyScheduler()})
        self.dataset_mgr = DatasetManager(self.dataset_db)

    def create(self, cls, **kwargs):
        try:
            exp = cls(self.device_mgr, self.dataset_mgr, **kwargs)
            exp.prepare()
            return exp
        except KeyError as e:
            # skip if ddb does not match requirements
            raise unittest.SkipTest(*e.args)

    def execute(self, cls, *args, **kwargs):
        expid = {
            "file": sys.modules[cls.__module__].__file__,
            "class_name": cls.__name__,
            "arguments": kwargs
        }
        self.device_mgr.virtual_devices["scheduler"].expid = expid
        try:
            exp = self.create(cls, **kwargs)
            exp.run()
            exp.analyze()
            return exp
        except CompileError as error:
            # Reduce amount of text on terminal.
            raise error from None
        finally:
            self.device_mgr.close_devices()
