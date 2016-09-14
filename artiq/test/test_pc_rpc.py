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
    def _run_server_and_test(self, test, *args):
        # running this file outside of unittest starts the echo server
        with subprocess.Popen([sys.executable,
                               sys.modules[__name__].__file__]) as proc:
            try:
                test(*args)
            finally:
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    raise

    def _blocking_echo(self, target):
        for attempt in range(100):
            time.sleep(.2)
            try:
                remote = pc_rpc.Client(test_address, test_port,
                                       target)
            except ConnectionRefusedError:
                pass
            else:
                break
        try:
            test_object_back = remote.echo(test_object)
            self.assertEqual(test_object, test_object_back)
            test_object_back = remote.async_echo(test_object)
            self.assertEqual(test_object, test_object_back)
            with self.assertRaises(AttributeError):
                remote.non_existing_method
            remote.terminate()
        finally:
            remote.close_rpc()

    def test_blocking_echo(self):
        self._run_server_and_test(self._blocking_echo, "test")

    def test_blocking_echo_autotarget(self):
        self._run_server_and_test(self._blocking_echo, pc_rpc.AutoTarget)

    async def _asyncio_echo(self, target):
        remote = pc_rpc.AsyncioClient()
        for attempt in range(100):
            await asyncio.sleep(.2)
            try:
                await remote.connect_rpc(test_address, test_port, target)
            except ConnectionRefusedError:
                pass
            else:
                break
        try:
            test_object_back = await remote.echo(test_object)
            self.assertEqual(test_object, test_object_back)
            test_object_back = await remote.async_echo(test_object)
            self.assertEqual(test_object, test_object_back)
            with self.assertRaises(AttributeError):
                await remote.non_existing_method
            await remote.terminate()
        finally:
            remote.close_rpc()

    def _loop_asyncio_echo(self, target):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._asyncio_echo(target))
        finally:
            loop.close()

    def test_asyncio_echo(self):
        self._run_server_and_test(self._loop_asyncio_echo, "test")

    def test_asyncio_echo_autotarget(self):
        self._run_server_and_test(self._loop_asyncio_echo, pc_rpc.AutoTarget)


class FireAndForgetCase(unittest.TestCase):
    def _set_ok(self):
        self.ok = True

    def test_fire_and_forget(self):
        self.ok = False
        p = fire_and_forget.FFProxy(self)
        p._set_ok()
        with self.assertRaises(AttributeError):
            p.non_existing_method
        p.ff_join()
        self.assertTrue(self.ok)


class Echo:
    def echo(self, x):
        return x

    async def async_echo(self, x):
        await asyncio.sleep(0.01)
        return x


def run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        echo = Echo()
        server = pc_rpc.Server({"test": echo}, builtin_terminate=True)
        loop.run_until_complete(server.start(test_address, test_port))
        try:
            loop.run_until_complete(server.wait_terminate())
        finally:
            loop.run_until_complete(server.stop())
    finally:
        loop.close()

if __name__ == "__main__":
    run_server()
