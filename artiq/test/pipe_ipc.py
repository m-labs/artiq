import unittest
import sys
import asyncio
import os

from artiq.protocols import pipe_ipc


class IPCCase(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    async def _coro_test(self, child_asyncio):
        ipc = pipe_ipc.AsyncioParentComm()
        await ipc.create_subprocess(sys.executable,
                                    sys.modules[__name__].__file__,
                                    str(child_asyncio),
                                    ipc.get_address())
        for i in range(10):
            ipc.write("{}\n".format(i).encode())
            await ipc.drain()
            s = (await ipc.readline()).decode()
            self.assertEqual(int(s), i+1)
        ipc.write(b"-1\n")
        await ipc.process.wait()
        ipc.close()

    def test_blocking(self):
        self.loop.run_until_complete(self._coro_test(False))

    def test_asyncio(self):
        self.loop.run_until_complete(self._coro_test(True))


def run_child_blocking():
    child_comm = pipe_ipc.ChildComm(sys.argv[2])
    while True:
        x = int(child_comm.readline().decode())
        if x < 0:
            break
        child_comm.write((str(x+1) + "\n").encode())
    child_comm.close()


async def coro_child():
    child_comm =  pipe_ipc.AsyncioChildComm(sys.argv[2])
    await child_comm.connect()
    while True:
       x = int((await child_comm.readline()).decode())
       if x < 0:
           break
       child_comm.write((str(x+1) + "\n").encode())
       await child_comm.drain()
    child_comm.close()


def run_child_asyncio():
    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    loop.run_until_complete(coro_child())
    loop.close()


def run_child():
    if sys.argv[1] == "True":
        run_child_asyncio()
    else:
        run_child_blocking()

if __name__ == "__main__":
    run_child()
