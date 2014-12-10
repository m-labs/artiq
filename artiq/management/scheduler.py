import asyncio
from time import time

from artiq.management.worker import Worker


class Scheduler:
    def __init__(self, *args, **kwargs):
        self.worker = Worker(*args, **kwargs)
        self.currently_executing = None
        self.next_rid = 0
        self.queued = []
        self.queue_count = asyncio.Semaphore(0)

    def new_rid(self):
        r = self.next_rid
        self.next_rid += 1
        return r

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
        rid = self.new_rid()
        self.queued.append((rid, run_params, timeout))
        self.queue_count.release()
        return rid

    def cancel_once(self, rid):
        idx = next(idx for idx, (qrid, _, _) in enumerate(self.queued)
                   if qrid == rid)
        del self.queued[idx]

    def get_schedule(self):
        if self.currently_executing is None:
            ce = None
        else:
            rid, run_params, timeout, t = self.currently_executing
            ce = rid, run_params, timeout, time() - t
        return ce, self.queued

    def run_periodic(self, run_params, timeout, period):
        raise NotImplementedError

    def cancel_periodic(self, prid):
        raise NotImplementedError

    @asyncio.coroutine
    def _run(self, rid, run_params, timeout):
        self.currently_executing = rid, run_params, timeout, time()
        result = yield from self.worker.run(run_params, timeout)
        self.currently_executing = None
        return result

    @asyncio.coroutine
    def _schedule(self):
        while True:
            yield from self.queue_count.acquire()
            rid, run_params, timeout = self.queued.pop(0)
            result = yield from self._run(rid, run_params, timeout)
            print(rid, result)
