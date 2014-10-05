import asyncio

from artiq.management.worker import Worker


class Scheduler:
    def __init__(self, loop):
        self.loop = loop
        self.queue = asyncio.Queue()

    def __enter__(self):
        self.worker = Worker(self.loop)
        return self

    def __exit__(self, type, value, traceback):
        self.loop.run_until_complete(self.worker.end_process())
        del self.worker

    def add_run_once(self, item, timeout):
        yield from self.queue.put((item, timeout))

    def task(self):
        while True:
            item, timeout = yield from self.queue.get()
            result = yield from self.worker.run(item, timeout)
            print(result)
