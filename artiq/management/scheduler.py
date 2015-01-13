import asyncio
from time import time

from artiq.management.sync_struct import Notifier
from artiq.management.worker import Worker


class Scheduler:
    def __init__(self, worker_handlers):
        self.worker = Worker(worker_handlers)
        self.next_rid = 0
        self.queue = Notifier([])
        self.queue_modified = asyncio.Event()
        self.periodic = Notifier(dict())
        self.periodic_modified = asyncio.Event()

    def new_rid(self):
        r = self.next_rid
        self.next_rid += 1
        return r

    def new_prid(self):
        prids = set(range(len(self.periodic.read) + 1))
        prids -= set(self.periodic.read.keys())
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
        self.queue.append((rid, run_params, timeout))
        self.queue_modified.set()
        return rid

    def cancel_once(self, rid):
        idx = next(idx for idx, (qrid, _, _)
                   in enumerate(self.queue.read)
                   if qrid == rid)
        if idx == 0:
            # Cannot cancel when already running
            raise NotImplementedError
        del self.queue[idx]

    def run_periodic(self, run_params, timeout, period):
        prid = self.new_prid()
        self.periodic[prid] = 0, run_params, timeout, period
        self.periodic_modified.set()
        return prid

    def cancel_periodic(self, prid):
        del self.periodic[prid]

    @asyncio.coroutine
    def _run(self, rid, run_params, timeout):
        try:
            yield from self.worker.run(run_params, timeout)
        except Exception as e:
            print("RID {} failed:".format(rid))
            print(e)
        else:
            print("RID {} completed successfully".format(rid))

    @asyncio.coroutine
    def _run_periodic(self):
        while True:
            min_next_run = None
            min_prid = None
            for prid, params in self.periodic.read.items():
                if min_next_run is None or params[0] < min_next_run:
                    min_next_run = params[0]
                    min_prid = prid

            now = time()

            if min_next_run is None:
                return None
            min_next_run -= now
            if min_next_run > 0:
                return min_next_run

            next_run, run_params, timeout, period = \
                self.periodic.read[min_prid]
            self.periodic[min_prid] = now + period, run_params, timeout, period

            rid = self.new_rid()
            self.queue.insert(0, (rid, run_params, timeout))
            yield from self._run(rid, run_params, timeout)
            del self.queue[0]

    @asyncio.coroutine
    def _schedule(self):
        while True:
            next_periodic = yield from self._run_periodic()
            if self.queue.read:
                rid, run_params, timeout = self.queue.read[0]
                yield from self._run(rid, run_params, timeout)
                del self.queue[0]
            else:
                self.queue_modified.clear()
                self.periodic_modified.clear()
                done, pend = yield from asyncio.wait(
                    [
                        self.queue_modified.wait(),
                        self.periodic_modified.wait()
                    ],
                    timeout=next_periodic,
                    return_when=asyncio.FIRST_COMPLETED)
