import asyncio
import logging
from enum import Enum
from time import time

from artiq.master.worker import Worker
from artiq.tools import (asyncio_wait_or_cancel, asyncio_queue_peek,
                         TaskObject, WaitSet)
from artiq.protocols.sync_struct import Notifier


logger = logging.getLogger(__name__)


class RunStatus(Enum):
    pending = 0
    flushing = 1
    preparing = 2
    prepare_done = 3
    running = 4
    run_done = 5
    analyzing = 6
    analyze_done = 7
    paused = 8


def _mk_worker_method(name):
    @asyncio.coroutine
    def worker_method(self, *args, **kwargs):
        if self.worker.closed.is_set():
            return True
        m = getattr(self.worker, name)
        try:
            return (yield from m(*args, **kwargs))
        except Exception as e:
            if isinstance(e, asyncio.CancelledError):
                raise
            if self.worker.closed.is_set():
                logger.debug("suppressing worker exception of terminated run",
                             exc_info=True)
                # Return completion on termination
                return True
            else:
                raise
    return worker_method


class Run:
    def __init__(self, rid, pipeline_name,
                 expid, priority, due_date, flush,
                 worker_handlers, notifier):
        # called through pool
        self.rid = rid
        self.pipeline_name = pipeline_name
        self.expid = expid
        self.priority = priority
        self.due_date = due_date
        self.flush = flush

        self.worker = Worker(worker_handlers)

        self._status = RunStatus.pending

        self._notifier = notifier
        self._notifier[self.rid] = {
            "pipeline": self.pipeline_name,
            "expid": self.expid,
            "priority": self.priority,
            "due_date": self.due_date,
            "flush": self.flush,
            "status": self._status.name
        }

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value
        if not self.worker.closed.is_set():
            self._notifier[self.rid]["status"] = self._status.name

    # The run with the largest priority_key is to be scheduled first
    def priority_key(self, now=None):
        if self.due_date is None:
            due_date_k = 0
        else:
            due_date_k = -self.due_date
        if now is not None and self.due_date is not None:
            runnable = int(now > self.due_date)
        else:
            runnable = 1
        return (runnable, self.priority, due_date_k, -self.rid)

    @asyncio.coroutine
    def close(self):
        # called through pool
        yield from self.worker.close()
        del self._notifier[self.rid]

    _build = _mk_worker_method("build")

    @asyncio.coroutine
    def build(self):
        yield from self._build(self.rid, self.pipeline_name, self.expid,
                               self.priority)

    prepare = _mk_worker_method("prepare")
    run = _mk_worker_method("run")
    resume = _mk_worker_method("resume")
    analyze = _mk_worker_method("analyze")
    write_results = _mk_worker_method("write_results")


class RIDCounter:
    def __init__(self, next_rid):
        self._next_rid = next_rid

    def get(self):
        rid = self._next_rid
        self._next_rid += 1
        return rid


class RunPool:
    def __init__(self, ridc, worker_handlers, notifier):
        self.runs = dict()
        self.submitted_cb = None

        self._ridc = ridc
        self._worker_handlers = worker_handlers
        self._notifier = notifier

    def submit(self, expid, priority, due_date, flush, pipeline_name):
        # called through scheduler
        rid = self._ridc.get()
        run = Run(rid, pipeline_name, expid, priority, due_date, flush,
                  self._worker_handlers, self._notifier)
        self.runs[rid] = run
        if self.submitted_cb is not None:
            self.submitted_cb()
        return rid

    @asyncio.coroutine
    def delete(self, rid):
        # called through deleter
        if rid not in self.runs:
            return
        yield from self.runs[rid].close()
        del self.runs[rid]


class PrepareStage(TaskObject):
    def __init__(self, flush_tracker, delete_cb, pool, outq):
        self.flush_tracker = flush_tracker
        self.delete_cb = delete_cb
        self.pool = pool
        self.outq = outq

        self.pool_submitted = asyncio.Event()
        self.pool.submitted_cb = lambda: self.pool_submitted.set()

    @asyncio.coroutine
    def _push_runs(self):
        """Pushes all runs that have no due date of have a due date in the
        past.

        Returns the time before the next schedulable run, or None if the
        pool is empty."""
        while True:
            now = time()
            pending_runs = filter(lambda r: r.status == RunStatus.pending,
                                  self.pool.runs.values())
            try:
                run = max(pending_runs, key=lambda r: r.priority_key(now))
            except ValueError:
                # pending_runs is an empty sequence
                return None
            if run.due_date is None or run.due_date < now:
                if run.flush:
                    run.status = RunStatus.flushing
                    yield from asyncio_wait_or_cancel(
                        [self.flush_tracker.wait_empty(),
                         run.worker.closed.wait()],
                        return_when=asyncio.FIRST_COMPLETED)
                    if run.worker.closed.is_set():
                        continue
                run.status = RunStatus.preparing
                self.flush_tracker.add(run.rid)
                try:
                    yield from run.build()
                    yield from run.prepare()
                except:
                    logger.warning("got worker exception in prepare stage, "
                                   "deleting RID %d",
                                   run.rid, exc_info=True)
                    self.delete_cb(run.rid)
                run.status = RunStatus.prepare_done
                yield from self.outq.put(run)
            else:
                return run.due_date - now

    @asyncio.coroutine
    def _do(self):
        while True:
            next_timed_in = yield from self._push_runs()
            if next_timed_in is None:
                # pool is empty - wait for something to be added to it
                yield from self.pool_submitted.wait()
            else:
                # wait for next_timed_in seconds, or until the pool is modified
                yield from asyncio_wait_or_cancel([self.pool_submitted.wait()],
                                                  timeout=next_timed_in)
            self.pool_submitted.clear()


class RunStage(TaskObject):
    def __init__(self, delete_cb, inq, outq):
        self.delete_cb = delete_cb
        self.inq = inq
        self.outq = outq

    @asyncio.coroutine
    def _do(self):
        stack = []

        while True:
            try:
                next_irun = asyncio_queue_peek(self.inq)
            except asyncio.QueueEmpty:
                next_irun = None
            if not stack or (
                    next_irun is not None and
                    next_irun.priority_key() > stack[-1].priority_key()):
                stack.append((yield from self.inq.get()))

            run = stack.pop()
            try:
                if run.status == RunStatus.paused:
                    run.status = RunStatus.running
                    completed = yield from run.resume()
                else:
                    run.status = RunStatus.running
                    completed = yield from run.run()
            except:
                logger.warning("got worker exception in run stage, "
                               "deleting RID %d",
                               run.rid, exc_info=True)
                self.delete_cb(run.rid)
            else:
                if completed:
                    run.status = RunStatus.run_done
                    yield from self.outq.put(run)
                else:
                    run.status = RunStatus.paused
                    stack.append(run)


class AnalyzeStage(TaskObject):
    def __init__(self, delete_cb, inq):
        self.delete_cb = delete_cb
        self.inq = inq

    @asyncio.coroutine
    def _do(self):
        while True:
            run = yield from self.inq.get()
            run.status = RunStatus.analyzing
            try:
                yield from run.analyze()
                yield from run.write_results()
            except:
                logger.warning("got worker exception in analyze stage, "
                               "deleting RID %d",
                               run.rid, exc_info=True)
                self.delete_cb(run.rid)
            run.status = RunStatus.analyze_done
            self.delete_cb(run.rid)


class Pipeline:
    def __init__(self, ridc, deleter, worker_handlers, notifier):
        flush_tracker = WaitSet()
        def delete_cb(rid):
            deleter.delete(rid)
            flush_tracker.discard(rid)
        self.pool = RunPool(ridc, worker_handlers, notifier)
        self._prepare = PrepareStage(flush_tracker, delete_cb,
                                     self.pool, asyncio.Queue(maxsize=1))
        self._run = RunStage(delete_cb,
                             self._prepare.outq, asyncio.Queue(maxsize=1))
        self._analyze = AnalyzeStage(delete_cb, self._run.outq)

    def start(self):
        self._prepare.start()
        self._run.start()
        self._analyze.start()

    @asyncio.coroutine
    def stop(self):
        # NB: restart of a stopped pipeline is not supported
        yield from self._analyze.stop()
        yield from self._run.stop()
        yield from self._prepare.stop()


class Deleter(TaskObject):
    def __init__(self, pipelines):
        self._pipelines = pipelines
        self._queue = asyncio.JoinableQueue()

    def delete(self, rid):
        logger.debug("delete request for RID %d", rid)
        self._queue.put_nowait(rid)

    @asyncio.coroutine
    def join(self):
        yield from self._queue.join()

    @asyncio.coroutine
    def _delete(self, rid):
        for pipeline in self._pipelines.values():
            if rid in pipeline.pool.runs:
                logger.debug("deleting RID %d...", rid)
                yield from pipeline.pool.delete(rid)
                logger.debug("deletion of RID %d completed", rid)
                break

    @asyncio.coroutine
    def _gc_pipelines(self):
        pipeline_names = list(self._pipelines.keys())
        for name in pipeline_names:
            if not self._pipelines[name].pool.runs:
                logger.debug("garbage-collecting pipeline '%s'...", name)
                yield from self._pipelines[name].stop()
                del self._pipelines[name]
                logger.debug("garbage-collection of pipeline '%s' completed",
                             name)

    @asyncio.coroutine
    def _do(self):
        while True:
            rid = yield from self._queue.get()
            yield from self._delete(rid)
            yield from self._gc_pipelines()
            self._queue.task_done()


class Scheduler:
    def __init__(self, next_rid, worker_handlers):
        self.notifier = Notifier(dict())

        self._pipelines = dict()
        self._worker_handlers = worker_handlers
        self._terminated = False

        self._ridc = RIDCounter(next_rid)
        self._deleter = Deleter(self._pipelines)

    def start(self):
        self._deleter.start()

    @asyncio.coroutine
    def stop(self):
        # NB: restart of a stopped scheduler is not supported
        self._terminated = True  # prevent further runs from being created
        for pipeline in self._pipelines.values():
            for rid in pipeline.pool.runs.keys():
                self._deleter.delete(rid)
        yield from self._deleter.join()
        yield from self._deleter.stop()
        if self._pipelines:
            logger.warning("some pipelines were not garbage-collected")

    def submit(self, pipeline_name, expid, priority, due_date, flush):
        if self._terminated:
            return
        try:
            pipeline = self._pipelines[pipeline_name]
        except KeyError:
            logger.debug("creating pipeline '%s'", pipeline_name)
            pipeline = Pipeline(self._ridc, self._deleter,
                                self._worker_handlers, self.notifier)
            self._pipelines[pipeline_name] = pipeline
            pipeline.start()
        return pipeline.pool.submit(expid, priority, due_date, flush, pipeline_name)

    def delete(self, rid):
        self._deleter.delete(rid)
