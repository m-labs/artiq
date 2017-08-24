import os, sys
import asyncio
import unittest
from artiq.protocols.pc_rpc import Server

class Target:
    def output_value(self):
        return 4125380

class rpctool_test(unittest.TestCase):
    async def check_value(self):
        proc = asyncio.create_subprocess_shell(
                            sys.executable + " -m artiq.frontend.artiq_rpctool ::1 3249 call output_value", 
                            stdout = asyncio.subprocess.PIPE,
                            stderr = None)
        result = await proc
        (value, err) = await result.communicate()
        self.assertEqual(value.decode('ascii').rstrip(), '4125380')
        await result.wait()

    async def do_test(self):
        server = Server({"target": Target()}, None, True, True)
        await server.start("::1", 3249)
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

    
