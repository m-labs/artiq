import asyncio

from artiq.management.worker import Worker


class Scheduler:
    def __init__(self):
        self.worker = Worker()
        self.queue = asyncio.Queue()

    @asyncio.coroutine
    def start(self):
        self.task = asyncio.Task(self._schedule())
        yield from self.worker.create_process()

    @asyncio.coroutine
    def stop(self):
        self.task.cancel()
        yield from asyncio.wait([self.task])
        del self.task
        yield from self.worker.end_process()

    def run_once(self, run_params, timeout):
        self.queue.put_nowait((run_params, timeout))

    @asyncio.coroutine
    def _schedule(self):
        while True:
            run_params, timeout = yield from self.queue.get()
            result = yield from self.worker.run(run_params, timeout)
            print(result)
