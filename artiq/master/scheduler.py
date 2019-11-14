import asyncio
import logging
from enum import Enum
from time import time

from sipyco.sync_struct import Notifier
from sipyco.asyncio_tools import TaskObject, Condition

from artiq.master.worker import Worker, log_worker_exception
from artiq.tools import asyncio_wait_or_cancel


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
    async def worker_method(self, *args, **kwargs):
        if self.worker.closed.is_set():
            return True
        m = getattr(self.worker, name)
        try:
            return await m(*args, **kwargs)
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
        self.termination_requested = False

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

    async def close(self):
        # called through pool
        await self.worker.close()
        del self._notifier[self.rid]

    _build = _mk_worker_method("build")

    async def build(self):
        await self._build(self.rid, self.pipeline_name,
                          self.wd, self.expid,
                          self.priority)

    prepare = _mk_worker_method("prepare")
    run = _mk_worker_method("run")
    resume = _mk_worker_method("resume")
    analyze = _mk_worker_method("analyze")
    write_results = _mk_worker_method("write_results")


class RunPool:
    def __init__(self, ridc, worker_handlers, notifier, experiment_db):
        self.runs = dict()
        self.state_changed = Condition()

        self.ridc = ridc
        self.worker_handlers = worker_handlers
        self.notifier = notifier
        self.experiment_db = experiment_db

    def submit(self, expid, priority, due_date, flush, pipeline_name):
        # mutates expid to insert head repository revision if None.
        # called through scheduler.
        rid = self.ridc.get()
        if "repo_rev" in expid:
            if expid["repo_rev"] is None:
                expid["repo_rev"] = self.experiment_db.cur_rev
            wd, repo_msg = self.experiment_db.repo_backend.request_rev(
                expid["repo_rev"])
        else:
            wd, repo_msg = None, None
        run = Run(rid, pipeline_name, wd, expid, priority, due_date, flush,
                  self, repo_msg=repo_msg)
        self.runs[rid] = run
        self.state_changed.notify()
        return rid

    async def delete(self, rid):
        # called through deleter
        if rid not in self.runs:
            return
        run = self.runs[rid]
        await run.close()
        if "repo_rev" in run.expid:
            self.experiment_db.repo_backend.release_rev(run.expid["repo_rev"])
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

    async def _do(self):
        while True:
            run = self._get_run()
            if run is None:
                await self.pool.state_changed.wait()
            elif isinstance(run, float):
                await asyncio_wait_or_cancel([self.pool.state_changed.wait()],
                                             timeout=run)
            else:
                if run.flush:
                    run.status = RunStatus.flushing
                    while not all(r.status in (RunStatus.pending,
                                               RunStatus.deleting)
                                  or r.priority < run.priority
                                  or r is run
                                  for r in self.pool.runs.values()):
                        ev = [self.pool.state_changed.wait(),
                              run.worker.closed.wait()]
                        await asyncio_wait_or_cancel(
                            ev, return_when=asyncio.FIRST_COMPLETED)
                        if run.worker.closed.is_set():
                            break
                    if run.worker.closed.is_set():
                        continue
                run.status = RunStatus.preparing
                try:
                    await run.build()
                    await run.prepare()
                except:
                    logger.error("got worker exception in prepare stage, "
                                 "deleting RID %d", run.rid)
                    log_worker_exception()
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

    async def _do(self):
        stack = []

        while True:
            next_irun = self._get_run()
            if not stack or (
                    next_irun is not None and
                    next_irun.priority_key() > stack[-1].priority_key()):
                while next_irun is None:
                    await self.pool.state_changed.wait()
                    next_irun = self._get_run()
                stack.append(next_irun)

            run = stack.pop()
            try:
                if run.status == RunStatus.paused:
                    run.status = RunStatus.running
                    # clear "termination requested" flag now
                    # so that if it is set again during the resume, this
                    # results in another exception.
                    request_termination = run.termination_requested
                    run.termination_requested = False
                    completed = await run.resume(request_termination)
                else:
                    run.status = RunStatus.running
                    completed = await run.run()
            except:
                logger.error("got worker exception in run stage, "
                             "deleting RID %d", run.rid)
                log_worker_exception()
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

    async def _do(self):
        while True:
            run = self._get_run()
            while run is None:
                await self.pool.state_changed.wait()
                run = self._get_run()
            run.status = RunStatus.analyzing
            try:
                await run.analyze()
            except:
                logger.error("got worker exception in analyze stage of RID %d."
                             " Results will still be saved.", run.rid)
                log_worker_exception()
            try:
                await run.write_results()
            except:
                logger.error("failed to write results of RID %d.", run.rid)
                log_worker_exception()
            self.delete_cb(run.rid)


class Pipeline:
    def __init__(self, ridc, deleter, worker_handlers, notifier, experiment_db):
        self.pool = RunPool(ridc, worker_handlers, notifier, experiment_db)
        self._prepare = PrepareStage(self.pool, deleter.delete)
        self._run = RunStage(self.pool, deleter.delete)
        self._analyze = AnalyzeStage(self.pool, deleter.delete)

    def start(self):
        self._prepare.start()
        self._run.start()
        self._analyze.start()

    async def stop(self):
        # NB: restart of a stopped pipeline is not supported
        await self._analyze.stop()
        await self._run.stop()
        await self._prepare.stop()


class Deleter(TaskObject):
    """Provides a synchronous interface for instigating deletion of runs.

    :meth:`RunPool.delete` is an async function (it needs to close the worker
    connection, etc.), so we maintain a queue of RIDs to delete on a background task.
    """
    def __init__(self, pipelines):
        self._pipelines = pipelines
        self._queue = asyncio.Queue()

    def delete(self, rid):
        """Delete the run with the given RID.

        Multiple calls for the same RID are silently ignored.
        """
        logger.debug("delete request for RID %d", rid)
        for pipeline in self._pipelines.values():
            if rid in pipeline.pool.runs:
                pipeline.pool.runs[rid].status = RunStatus.deleting
                break
        self._queue.put_nowait(rid)

    async def join(self):
        await self._queue.join()

    async def _delete(self, rid):
        # By looking up the run by RID, we implicitly make sure to delete each run only
        # once.
        for pipeline in self._pipelines.values():
            if rid in pipeline.pool.runs:
                logger.debug("deleting RID %d...", rid)
                await pipeline.pool.delete(rid)
                logger.debug("deletion of RID %d completed", rid)
                break

    async def _gc_pipelines(self):
        pipeline_names = list(self._pipelines.keys())
        for name in pipeline_names:
            if not self._pipelines[name].pool.runs:
                logger.debug("garbage-collecting pipeline '%s'...", name)
                await self._pipelines[name].stop()
                del self._pipelines[name]
                logger.debug("garbage-collection of pipeline '%s' completed",
                             name)

    async def _do(self):
        while True:
            rid = await self._queue.get()
            await self._delete(rid)
            await self._gc_pipelines()
            self._queue.task_done()


class Scheduler:
    def __init__(self, ridc, worker_handlers, experiment_db):
        self.notifier = Notifier(dict())

        self._pipelines = dict()
        self._worker_handlers = worker_handlers
        self._experiment_db = experiment_db
        self._terminated = False

        self._ridc = ridc
        self._deleter = Deleter(self._pipelines)

    def start(self):
        self._deleter.start()

    async def stop(self):
        # NB: restart of a stopped scheduler is not supported
        self._terminated = True  # prevent further runs from being created
        for pipeline in self._pipelines.values():
            for rid in pipeline.pool.runs.keys():
                self._deleter.delete(rid)
        await self._deleter.join()
        await self._deleter.stop()
        if self._pipelines:
            logger.warning("some pipelines were not garbage-collected")

    def submit(self, pipeline_name, expid, priority=0, due_date=None, flush=False):
        """Submits a new run.

        When called through an experiment, the default values of
        ``pipeline_name``, ``expid`` and ``priority`` correspond to those of
        the current run."""
        # mutates expid to insert head repository revision if None
        if self._terminated:
            return
        try:
            pipeline = self._pipelines[pipeline_name]
        except KeyError:
            logger.debug("creating pipeline '%s'", pipeline_name)
            pipeline = Pipeline(self._ridc, self._deleter,
                                self._worker_handlers, self.notifier,
                                self._experiment_db)
            self._pipelines[pipeline_name] = pipeline
            pipeline.start()
        return pipeline.pool.submit(expid, priority, due_date, flush, pipeline_name)

    def delete(self, rid):
        """Kills the run with the specified RID."""
        self._deleter.delete(rid)

    def request_termination(self, rid):
        """Requests graceful termination of the run with the specified RID."""
        for pipeline in self._pipelines.values():
            if rid in pipeline.pool.runs:
                run = pipeline.pool.runs[rid]
                if run.status == RunStatus.running or run.status == RunStatus.paused:
                    run.termination_requested = True
                else:
                    self.delete(rid)
                break

    def get_status(self):
        """Returns a dictionary containing information about the runs currently
        tracked by the scheduler.

        Must not be modified."""
        return self.notifier.raw_view

    def check_pause(self, rid):
        """Returns ``True`` if there is a condition that could make ``pause``
        not return immediately (termination requested or higher priority run).

        The typical purpose of this function is to check from a kernel
        whether returning control to the host and pausing would have an effect,
        in order to avoid the cost of switching kernels in the common case
        where ``pause`` does nothing.

        This function does not have side effects, and does not have to be
        followed by a call to ``pause``.
        """
        for pipeline in self._pipelines.values():
            if rid in pipeline.pool.runs:
                run = pipeline.pool.runs[rid]
                if run.status != RunStatus.running:
                    return False
                if run.termination_requested:
                    return True

                prepared_runs = filter(lambda r: r.status == RunStatus.prepare_done,
                                       pipeline.pool.runs.values())
                try:
                    r = max(prepared_runs, key=lambda r: r.priority_key())
                except ValueError:
                    # prepared_runs is an empty sequence
                    return False
                return r.priority_key() > run.priority_key()
        raise KeyError("RID not found")
