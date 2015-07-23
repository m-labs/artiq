import unittest
import sys
import subprocess
import asyncio
import time

import numpy as np

from artiq.protocols import pc_rpc, fire_and_forget


test_address = "::1"
test_port = 7777
test_object = [5, 2.1, None, True, False,
               {"a": 5, 2: np.linspace(0, 10, 1)},
               (4, 5), (10,), "ab\nx\"'"]


class RPCCase(unittest.TestCase):
    def _run_server_and_test(self, test):
        # running this file outside of unittest starts the echo server
        with subprocess.Popen([sys.executable,
                               sys.modules[__name__].__file__]) as proc:
            try:
                test()
            finally:
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    raise

    def _blocking_echo(self):
        for attempt in range(100):
            time.sleep(.2)
            try:
                remote = pc_rpc.Client(test_address, test_port,
                                       "test")
            except ConnectionRefusedError:
                pass
            else:
                break
        try:
            test_object_back = remote.echo(test_object)
            self.assertEqual(test_object, test_object_back)
            with self.assertRaises(pc_rpc.RemoteError):
                remote.non_existing_method()
            remote.quit()
        finally:
            remote.close_rpc()

    def test_blocking_echo(self):
        self._run_server_and_test(self._blocking_echo)

    @asyncio.coroutine
    def _asyncio_echo(self):
        remote = pc_rpc.AsyncioClient()
        for attempt in range(100):
            yield from asyncio.sleep(.2)
            try:
                yield from remote.connect_rpc(test_address, test_port, "test")
            except ConnectionRefusedError:
                pass
            else:
                break
        try:
            test_object_back = yield from remote.echo(test_object)
            self.assertEqual(test_object, test_object_back)
            with self.assertRaises(pc_rpc.RemoteError):
                yield from remote.non_existing_method()
            yield from remote.quit()
        finally:
            remote.close_rpc()

    def _loop_asyncio_echo(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._asyncio_echo())
        finally:
            loop.close()

    def test_asyncio_echo(self):
        self._run_server_and_test(self._loop_asyncio_echo)


class FireAndForgetCase(unittest.TestCase):
    def _set_ok(self):
        self.ok = True

    def test_fire_and_forget(self):
        self.ok = False
        p = fire_and_forget.FFProxy(self)
        p._set_ok()
        p.ff_join()
        self.assertTrue(self.ok)


class Echo:
    def __init__(self):
        self.terminate_notify = asyncio.Semaphore(0)

    @asyncio.coroutine
    def wait_quit(self):
        yield from self.terminate_notify.acquire()

    def quit(self):
        self.terminate_notify.release()

    def echo(self, x):
        return x


def run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        echo = Echo()
        server = pc_rpc.Server({"test": echo})
        loop.run_until_complete(server.start(test_address, test_port))
        try:
            loop.run_until_complete(echo.wait_quit())
        finally:
            loop.run_until_complete(server.stop())
    finally:
        loop.close()

if __name__ == "__main__":
    run_server()
