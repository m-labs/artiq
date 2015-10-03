import asyncio
import logging
from enum import Enum
from time import time

from artiq.master.worker import Worker
from artiq.tools import asyncio_wait_or_cancel, TaskObject, Condition
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
    deleting = 7
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
                 wd, expid, priority, due_date, flush,
                 pool, **kwargs):
        # called through pool
        self.rid = rid
        self.pipeline_name = pipeline_name
        self.wd = wd
        self.expid = expid
        self.priority = priority
        self.due_date = due_date
        self.flush = flush

        self.worker = Worker(pool.worker_handlers)

        self._status = RunStatus.pending

        notification = {
            "pipeline": self.pipeline_name,
            "expid": self.expid,
            "priority": self.priority,
            "due_date": self.due_date,
            "flush": self.flush,
            "status": self._status.name
        }
        notification.update(kwargs)
        self._notifier = pool.notifier
        self._notifier[self.rid] = notification
        self._state_changed = pool.state_changed

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value
        if not self.worker.closed.is_set():
            self._notifier[self.rid]["status"] = self._status.name
        self._state_changed.notify()

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
        yield from self._build(self.rid, self.pipeline_name,
                               self.wd, self.expid,
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
    def __init__(self, ridc, worker_handlers, notifier, repo_backend):
        self.runs = dict()
        self.state_changed = Condition()

        self.ridc = ridc
        self.worker_handlers = worker_handlers
        self.notifier = notifier
        self.repo_backend = repo_backend

    def submit(self, expid, priority, due_date, flush, pipeline_name):
        # mutates expid to insert head repository revision if None.
        # called through scheduler.
        rid = self.ridc.get()
        if "repo_rev" in expid:
            if expid["repo_rev"] is None:
                expid["repo_rev"] = self.repo_backend.get_head_rev()
            wd, repo_msg = self.repo_backend.request_rev(expid["repo_rev"])
        else:
            wd, repo_msg = None, None
        run = Run(rid, pipeline_name, wd, expid, priority, due_date, flush,
                  self, repo_msg=repo_msg)
        self.runs[rid] = run
        self.state_changed.notify()
        return rid

    @asyncio.coroutine
    def delete(self, rid):
        # called through deleter
        if rid not in self.runs:
            return
        run = self.runs[rid]
        yield from run.close()
        if "repo_rev" in run.expid:
            self.repo_backend.release_rev(run.expid["repo_rev"])
        del self.runs[rid]


class PrepareStage(TaskObject):
    def __init__(self, pool, delete_cb):
        self.pool = pool
        self.delete_cb = delete_cb

    def _get_run(self):
        """If a run should get prepared now, return it.
        Otherwise, return a float representing the time before the next timed
        run becomes due, or None if there is no such run."""
        now = time()
        pending_runs = filter(lambda r: r.status == RunStatus.pending,
                              self.pool.runs.values())
        try:
            candidate = max(pending_runs, key=lambda r: r.priority_key(now))
        except ValueError:
            # pending_runs is an empty sequence
            return None

        prepared_runs = filter(lambda r: r.status == RunStatus.prepare_done,
                               self.pool.runs.values())
        try:
            top_prepared_run = max(prepared_runs,
                                   key=lambda r: r.priority_key())
        except ValueError:
            # there are no existing prepared runs - go ahead with <candidate>
            pass
        else:
            # prepare <candidate> (as well) only if it has higher priority than
            # the highest priority prepared run
            if top_prepared_run.priority_key() >= candidate.priority_key():
                return None

        if candidate.due_date is None or candidate.due_date < now:
            return candidate
        else:
            return candidate.due_date - now

    @asyncio.coroutine
    def _do(self):
        while True:
            run = self._get_run()
            if run is None:
                yield from self.pool.state_changed.wait()
            elif isinstance(run, float):
                yield from asyncio_wait_or_cancel([self.pool.state_changed.wait()],
                                                  timeout=run)
            else:
                if run.flush:
                    run.status = RunStatus.flushing
                    while not all(r.status in (RunStatus.pending,
                                               RunStatus.deleting)
                                  or r is run
                                  for r in self.pool.runs.values()):
                        ev = [self.pool.state_changed.wait(),
                              run.worker.closed.wait()]
                        yield from asyncio_wait_or_cancel(
                            ev, return_when=asyncio.FIRST_COMPLETED)
                        if run.worker.closed.is_set():
                            break
                    if run.worker.closed.is_set():
                            continue
                run.status = RunStatus.preparing
                try:
                    yield from run.build()
                    yield from run.prepare()
                except:
                    logger.warning("got worker exception in prepare stage, "
                                   "deleting RID %d",
                                   run.rid, exc_info=True)
                    self.delete_cb(run.rid)
                else:
                    run.status = RunStatus.prepare_done


class RunStage(TaskObject):
    def __init__(self, pool, delete_cb):
        self.pool = pool
        self.delete_cb = delete_cb

    def _get_run(self):
        prepared_runs = filter(lambda r: r.status == RunStatus.prepare_done,
                               self.pool.runs.values())
        try:
            r = max(prepared_runs, key=lambda r: r.priority_key())
        except ValueError:
            # prepared_runs is an empty sequence
            r = None
        return r

    @asyncio.coroutine
    def _do(self):
        stack = []

        while True:
            next_irun = self._get_run()
            if not stack or (
                    next_irun is not None and
                    next_irun.priority_key() > stack[-1].priority_key()):
                while next_irun is None:
                    yield from self.pool.state_changed.wait()
                    next_irun = self._get_run()
                stack.append(next_irun)

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
                else:
                    run.status = RunStatus.paused
                    stack.append(run)


class AnalyzeStage(TaskObject):
    def __init__(self, pool, delete_cb):
        self.pool = pool
        self.delete_cb = delete_cb

    def _get_run(self):
        run_runs = filter(lambda r: r.status == RunStatus.run_done,
                          self.pool.runs.values())
        try:
            r = max(run_runs, key=lambda r: r.priority_key())
        except ValueError:
            # run_runs is an empty sequence
            r = None
        return r

    @asyncio.coroutine
    def _do(self):
        while True:
            run = self._get_run()
            while run is None:
                yield from self.pool.state_changed.wait()
                run = self._get_run()
            run.status = RunStatus.analyzing
            try:
                yield from run.analyze()
                yield from run.write_results()
            except:
                logger.warning("got worker exception in analyze stage, "
                               "deleting RID %d",
                               run.rid, exc_info=True)
                self.delete_cb(run.rid)
            else:
                self.delete_cb(run.rid)


class Pipeline:
    def __init__(self, ridc, deleter, worker_handlers, notifier, repo_backend):
        self.pool = RunPool(ridc, worker_handlers, notifier, repo_backend)
        self._prepare = PrepareStage(self.pool, deleter.delete)
        self._run = RunStage(self.pool, deleter.delete)
        self._analyze = AnalyzeStage(self.pool, deleter.delete)

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
        self._queue = asyncio.Queue()

    def delete(self, rid):
        logger.debug("delete request for RID %d", rid)
        for pipeline in self._pipelines.values():
            if rid in pipeline.pool.runs:
                pipeline.pool.runs[rid].status = RunStatus.deleting
                break
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
    def __init__(self, next_rid, worker_handlers, repo_backend):
        self.notifier = Notifier(dict())

        self._pipelines = dict()
        self._worker_handlers = worker_handlers
        self._repo_backend = repo_backend
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
        # mutates expid to insert head repository revision if None
        if self._terminated:
            return
        try:
            pipeline = self._pipelines[pipeline_name]
        except KeyError:
            logger.debug("creating pipeline '%s'", pipeline_name)
            pipeline = Pipeline(self._ridc, self._deleter,
                                self._worker_handlers, self.notifier,
                                self._repo_backend)
            self._pipelines[pipeline_name] = pipeline
            pipeline.start()
        return pipeline.pool.submit(expid, priority, due_date, flush, pipeline_name)

    def delete(self, rid):
        self._deleter.delete(rid)
