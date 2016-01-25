import unittest
import sys
import asyncio

from artiq.protocols import pipe_ipc


class IPCCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    async def _coro_test(self, child_blocking):
        ipc = pipe_ipc.AsyncioParentComm()
        await ipc.create_subprocess(sys.executable,
                                    sys.modules[__name__].__file__,
                                    ipc.get_address())
        for i in range(10):
            ipc.write("{}\n".format(i).encode())
            s = (await ipc.readline()).decode()
            self.assertEqual(int(s), i+1)
        ipc.write(b"-1\n")
        await ipc.process.wait()
        ipc.close()

    def test_blocking(self):
        self.loop.run_until_complete(self._coro_test(True))


def run_child():
    child_comm = pipe_ipc.ChildComm(sys.argv[1])
    while True:
        x = int(child_comm.readline().decode())
        if x < 0:
            break
        child_comm.write((str(x+1) + "\n").encode())

if __name__ == "__main__":
    run_child()
