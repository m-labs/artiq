import unittest
import asyncio

from artiq.protocols import sync_struct

test_address = "::1"
test_port = 7777


@asyncio.coroutine
def write_test_data(test_dict):
    for i in range(10):
        test_dict[str(i)] = i
    test_dict["Finished"] = True


@asyncio.coroutine
def start_server(publisher_future, test_dict_future):
    test_dict = sync_struct.Notifier(dict())
    publisher = sync_struct.Publisher(
        {"test": test_dict})
    yield from publisher.start(test_address, test_port)
    publisher_future.set_result(publisher)
    test_dict_future.set_result(test_dict)


class SyncStructCase(unittest.TestCase):
    def init_test_dict(self, init):
        self.test_dict = init
        return init

    @asyncio.coroutine
    def do_recv(self):
        while not hasattr(self, "test_dict")\
                or "Finished" not in self.test_dict.keys():
            yield from asyncio.sleep(0.5)

    def test_recv(self):
        self.loop = loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        publisher = asyncio.Future()
        test_dict = asyncio.Future()
        asyncio.async(start_server(publisher, test_dict))
        loop.run_until_complete(publisher)
        loop.run_until_complete(test_dict)

        self.publisher = publisher.result()
        test_dict = test_dict.result()
        test_vector = dict()
        loop.run_until_complete(write_test_data(test_vector))

        asyncio.async(write_test_data(test_dict))
        self.subscriber = sync_struct.Subscriber("test", self.init_test_dict)
        loop.run_until_complete(self.subscriber.connect(test_address,
                                                        test_port))
        loop.run_until_complete(self.do_recv())
        self.assertEqual(self.test_dict, test_vector)

    def tearDown(self):
        self.loop.run_until_complete(self.subscriber.close())
        self.loop.run_until_complete(self.publisher.stop())
        self.loop.close()
