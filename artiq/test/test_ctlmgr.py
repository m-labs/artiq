import os
import sys
import unittest
import logging
import asyncio

from artiq.devices.ctlmgr import Controllers
from artiq.protocols.pc_rpc import AsyncioClient

logger = logging.getLogger(__name__)


class ControllerCase(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.addCleanup(self.loop.close)

        self.controllers = Controllers()
        self.controllers.host_filter = "::1"
        self.addCleanup(
            self.loop.run_until_complete, self.controllers.shutdown())

    async def start(self, name, entry):
        self.controllers[name] = entry
        await self.controllers.queue.join()
        await self.wait_for_ping(entry["host"], entry["port"])

    async def get_client(self, host, port):
        remote = AsyncioClient()
        await remote.connect_rpc(host, port, None)
        targets, _ = remote.get_rpc_id()
        await remote.select_rpc_target(targets[0])
        self.addCleanup(remote.close_rpc)
        return remote

    async def wait_for_ping(self, host, port, retries=5, timeout=2):
        dt = timeout/retries
        while timeout > 0:
            try:
                remote = await self.get_client(host, port)
                ok = await asyncio.wait_for(remote.ping(), dt)
                if not ok:
                    raise ValueError("unexcepted ping() response from "
                                     "controller: `{}`".format(ok))
                return ok
            except asyncio.TimeoutError:
                timeout -= dt
            except (ConnectionAbortedError, ConnectionError,
                    ConnectionRefusedError, ConnectionResetError):
                await asyncio.sleep(dt)
                timeout -= dt
        raise asyncio.TimeoutError

    def test_start_ping_stop_controller(self):
        entry = {
            "type": "controller",
            "host": "::1",
            "port": 3253,
            "command": (sys.executable.replace("\\", "\\\\")
                        + " -m artiq.frontend.lda_controller "
                        + "-p {port} --simulation")
        }
        async def test():
            await self.start("lda_sim", entry)
            remote = await self.get_client(entry["host"], entry["port"])
            await remote.ping()

        self.loop.run_until_complete(test())
