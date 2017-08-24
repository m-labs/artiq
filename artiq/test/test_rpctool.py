from artiq.protocols.pc_rpc import Server
import asyncio
import sys
import unittest

class Target:
    def message(self):
        return 4

class Rpctool_test(unittest.TestCase):
    async def get_message(self):
        proc = asyncio.create_subprocess_shell(
                            sys.executable + " -m artiq.frontend.artiq_rpctool ::1 3249 call message", 
                            stdout = asyncio.subprocess.PIPE,
                            stderr = asyncio.subprocess.PIPE)
        result = await proc
        (value, err) = await result.communicate()
        self.assertEqual(value.decode('ascii').rstrip(), '4')
        await result.wait()

    async def start(self):
        server = Server({"target": Target()}, None, True, True)
        await server.start("::1", 3249)
        await self.get_message()
        await server.stop()
        
    def test_rpc(self):
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.start())
        finally:
            loop.close()

    
