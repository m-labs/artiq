import unittest
import asyncio
import numpy as np

from artiq.protocols import sync_struct

test_address = "::1"
test_port = 7777


def write_test_data(test_dict):
    test_values = [5, 2.1, None, True, False,
                   {"a": 5, 2: np.linspace(0, 10, 1)},
                   (4, 5), (10,), "ab\nx\"'"]
    for i in range(10):
        test_dict[str(i)] = i
    for key, value in enumerate(test_values):
        test_dict[key] = value
    test_dict[1.5] = 1.5
    test_dict["array"] = []
    test_dict["array"].append(42)
    test_dict["array"].insert(1, 1)
    test_dict[100] = 0
    test_dict[100] = 1
    test_dict[101] = 1
    test_dict.pop(101)
    test_dict[102] = 1
    del test_dict[102]
    test_dict["finished"] = True


async def start_server(publisher_future, test_dict_future):
    test_dict = sync_struct.Notifier(dict())
    publisher = sync_struct.Publisher(
        {"test": test_dict})
    await publisher.start(test_address, test_port)
    publisher_future.set_result(publisher)
    test_dict_future.set_result(test_dict)


class SyncStructCase(unittest.TestCase):
    def init_test_dict(self, init):
        self.test_dict = init
        return init

    def notify(self, mod):
        if ((mod["action"] == "init" and "finished" in mod["struct"])
                or (mod["action"] == "setitem" and mod["key"] == "finished")):
            self.receiving_done.set()

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_recv(self):
        loop = self.loop
        self.receiving_done = asyncio.Event()
        publisher = asyncio.Future()
        test_dict = asyncio.Future()
        asyncio.ensure_future(start_server(publisher, test_dict))
        loop.run_until_complete(publisher)
        loop.run_until_complete(test_dict)

        self.publisher = publisher.result()
        test_dict = test_dict.result()
        test_vector = dict()
        write_test_data(test_vector)

        write_test_data(test_dict)
        self.subscriber = sync_struct.Subscriber("test", self.init_test_dict,
                                                 self.notify)
        loop.run_until_complete(self.subscriber.connect(test_address,
                                                        test_port))
        loop.run_until_complete(self.receiving_done.wait())
        self.assertEqual(self.test_dict, test_vector)
        self.loop.run_until_complete(self.subscriber.close())
        self.loop.run_until_complete(self.publisher.stop())

    def tearDown(self):
        self.loop.close()
