import asyncio

from artiq.management.worker import Worker


class Scheduler:
    def __init__(self, *args, **kwargs):
        self.worker = Worker(*args, **kwargs)
        self.queued = []
        self.queue_count = asyncio.Semaphore(0)

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
        self.queued.append((run_params, timeout))
        self.queue_count.release()

    @asyncio.coroutine
    def _schedule(self):
        while True:
            yield from self.queue_count.acquire()
            run_params, timeout = self.queued.pop(0)
            result = yield from self.worker.run(run_params, timeout)
            print(result)
