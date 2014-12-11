import asyncio
from time import time

from artiq.management.worker import Worker


class Scheduler:
    def __init__(self, *args, **kwargs):
        self.worker = Worker(*args, **kwargs)
        self.next_rid = 0
        self.currently_executing = None
        self.queued = []
        self.queue_count = asyncio.Semaphore(0)
        self.periodic = dict()
        self.periodic_modified = asyncio.Event()

    def new_rid(self):
        r = self.next_rid
        self.next_rid += 1
        return r

    def new_prid(self):
        prids = set(range(len(self.periodic) + 1))
        prids -= set(self.periodic.keys())
        return next(iter(prids))

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
        return ce, self.queued, self.periodic

    def run_periodic(self, run_params, timeout, period):
        prid = self.new_prid()
        self.periodic[prid] = 0, run_params, timeout, period
        self.periodic_modified.set()
        return prid

    def cancel_periodic(self, prid):
        del self.periodic[prid]

    @asyncio.coroutine
    def _run(self, rid, run_params, timeout):
        self.currently_executing = rid, run_params, timeout, time()
        result = yield from self.worker.run(run_params, timeout)
        self.currently_executing = None
        return result

    @asyncio.coroutine
    def _run_periodic(self):
        while True:
            min_next_run = None
            min_prid = None
            for prid, params in self.periodic.items():
                if min_next_run is None or params[0] < min_next_run:
                    min_next_run = params[0]
                    min_prid = prid

            now = time()

            if min_next_run is None:
                return None
            min_next_run -= now
            if min_next_run > 0:
                return min_next_run

            next_run, run_params, timeout, period = self.periodic[min_prid]
            self.periodic[min_prid] = now + period, run_params, timeout, period

            rid = self.new_rid()
            result = yield from self._run(rid, run_params, timeout)
            print(prid, rid, result)

    @asyncio.coroutine
    def _schedule(self):
        while True:
            next_periodic = yield from self._run_periodic()
            ev_queue = asyncio.Task(self.queue_count.acquire())
            ev_periodic = asyncio.Task(self.periodic_modified.wait())
            done, pend = yield from asyncio.wait(
                [ev_queue, ev_periodic],
                timeout=next_periodic,
                return_when=asyncio.FIRST_COMPLETED)
            for t in pend:
                t.cancel()

            yield from self._run_periodic()
            if ev_queue in done:
                rid, run_params, timeout = self.queued.pop(0)
                result = yield from self._run(rid, run_params, timeout)
                print(rid, result)
