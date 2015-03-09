import asyncio
from time import time

from artiq.protocols.sync_struct import Notifier
from artiq.master.worker import Worker


class Scheduler:
    def __init__(self, run_cb, first_rid):
        self.run_cb = run_cb
        self.worker = Worker()
        self.next_rid = first_rid
        self.queue = Notifier([])
        self.queue_modified = asyncio.Event()
        self.timed = Notifier(dict())
        self.timed_modified = asyncio.Event()

    def new_rid(self):
        r = self.next_rid
        self.next_rid += 1
        return r

    def new_trid(self):
        trids = set(range(len(self.timed.read) + 1))
        trids -= set(self.timed.read.keys())
        return next(iter(trids))

    def start(self):
        self.task = asyncio.Task(self._schedule())

    @asyncio.coroutine
    def stop(self):
        self.task.cancel()
        yield from asyncio.wait([self.task])
        del self.task

    def run_queued(self, run_params):
        rid = self.new_rid()
        self.queue.append((rid, run_params))
        self.queue_modified.set()
        return rid

    def cancel_queued(self, rid):
        idx = next(idx for idx, (qrid, _)
                   in enumerate(self.queue.read)
                   if qrid == rid)
        if idx == 0:
            # Cannot cancel when already running
            raise NotImplementedError
        del self.queue[idx]

    def run_timed(self, run_params, next_run):
        if next_run is None:
            next_run = time()
        trid = self.new_trid()
        self.timed[trid] = next_run, run_params
        self.timed_modified.set()
        return trid

    def cancel_timed(self, trid):
        del self.timed[trid]

    @asyncio.coroutine
    def _run(self, rid, run_params):
        self.run_cb(rid, run_params)
        try:
            yield from self.worker.prepare(rid, run_params)
            try:
                yield from self.worker.run()
                yield from self.worker.analyze()
            finally:
                yield from self.worker.close()
        except Exception as e:
            print("RID {} failed:".format(rid))
            print(e)
        else:
            print("RID {} completed successfully".format(rid))

    @asyncio.coroutine
    def _run_timed(self):
        while True:
            min_next_run = None
            min_trid = None
            for trid, params in self.timed.read.items():
                if min_next_run is None or params[0] < min_next_run:
                    min_next_run = params[0]
                    min_trid = trid

            now = time()

            if min_next_run is None:
                return None
            min_next_run -= now
            if min_next_run > 0:
                return min_next_run

            next_run, run_params = self.timed.read[min_trid]
            del self.timed[min_trid]

            rid = self.new_rid()
            self.queue.insert(0, (rid, run_params))
            yield from self._run(rid, run_params)
            del self.queue[0]

    @asyncio.coroutine
    def _schedule(self):
        while True:
            next_timed = yield from self._run_timed()
            if self.queue.read:
                rid, run_params = self.queue.read[0]
                yield from self._run(rid, run_params)
                del self.queue[0]
            else:
                self.queue_modified.clear()
                self.timed_modified.clear()
                t1 = asyncio.Task(self.queue_modified.wait())
                t2 = asyncio.Task(self.timed_modified.wait())
                try:
                    done, pend = yield from asyncio.wait(
                        [t1, t2],
                        timeout=next_timed,
                        return_when=asyncio.FIRST_COMPLETED)
                except:
                    t1.cancel()
                    t2.cancel()
                    raise
                for t in pend:
                    t.cancel()
