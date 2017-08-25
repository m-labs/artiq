import os, sys
import asyncio
import unittest

from artiq.protocols.pc_rpc import Server

class Target:
    def output_value(self):
        return 4125380

class TestRPCTool(unittest.TestCase):
    async def check_value(self):
        proc = await asyncio.create_subprocess_exec(
                            sys.executable, "-m", "artiq.frontend.artiq_rpctool", "::1", "7777", "call", "output_value",
                            stdout = asyncio.subprocess.PIPE)
        (value, err) = await proc.communicate()
        self.assertEqual(value.decode('ascii').rstrip(), '4125380')
        await proc.wait()

    async def do_test(self):
        server = Server({"target": Target()}, None, True, True)
        await server.start("::1", 7777)
        await self.check_value()
        await server.stop()

    def test_rpc(self):
        if os.name == "nt":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.do_test())
        finally:
            loop.close()

