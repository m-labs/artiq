import unittest
import sys
import subprocess
import asyncio
import time

import numpy as np

from artiq.management import pc_rpc


test_address = "::1"
test_port = 7777


class RPCCase(unittest.TestCase):
    def test_echo(self):
        # running this file outside of unittest starts the echo server
        with subprocess.Popen([sys.executable,
                               sys.modules[__name__].__file__]) as proc:
            try:
                test_object = [5, 2.1, None, True, False,
                               {"a": 5, 2: np.linspace(0, 10, 1)},
                               (4, 5), (10,), "ab\nx\"'"]
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
                    with self.assertRaises(pc_rpc.RemoteError):
                        remote.non_existing_method()
                    remote.quit()
                finally:
                    remote.close_rpc()
            finally:
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    raise
            self.assertEqual(test_object, test_object_back)


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
    loop = asyncio.get_event_loop()
    try:
        echo = Echo()
        server = pc_rpc.Server(echo, "test")
        loop.run_until_complete(server.start(test_address, test_port))
        try:
            loop.run_until_complete(echo.wait_quit())
        finally:
            loop.run_until_complete(server.stop())
    finally:
        loop.close()

if __name__ == "__main__":
    run_server()
