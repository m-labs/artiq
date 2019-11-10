import sys
import os
import asyncio
import logging
import subprocess
import time

from sipyco import pipe_ipc, pyon
from sipyco.logging_tools import LogParser
from sipyco.packed_exceptions import current_exc_packed

from artiq.tools import asyncio_wait_or_cancel


logger = logging.getLogger(__name__)


class WorkerTimeout(Exception):
    pass


class WorkerWatchdogTimeout(Exception):
    pass


class WorkerError(Exception):
    pass


class WorkerInternalException(Exception):
    """Exception raised inside the worker, information has been printed
    through logging."""
    pass


def log_worker_exception():
    exc, _, _ = sys.exc_info()
    if exc is WorkerInternalException:
        logger.debug("worker exception details", exc_info=True)
    else:
        logger.error("worker exception details", exc_info=True)


class Worker:
    def __init__(self, handlers=dict(), send_timeout=10.0):
        self.handlers = handlers
        self.send_timeout = send_timeout

        self.rid = None
        self.filename = None
        self.ipc = None
        self.watchdogs = dict()  # wid -> expiration (using time.monotonic)

        self.io_lock = asyncio.Lock()
        self.closed = asyncio.Event()

    def create_watchdog(self, t):
        n_user_watchdogs = len(self.watchdogs)
        if -1 in self.watchdogs:
            n_user_watchdogs -= 1
        avail = set(range(n_user_watchdogs + 1)) \
            - set(self.watchdogs.keys())
        wid = next(iter(avail))
        self.watchdogs[wid] = time.monotonic() + t
        return wid

    def delete_watchdog(self, wid):
        del self.watchdogs[wid]

    def watchdog_time(self):
        if self.watchdogs:
            return min(self.watchdogs.values()) - time.monotonic()
        else:
            return None

    def _get_log_source(self):
        return "worker({},{})".format(self.rid, self.filename)

    async def _create_process(self, log_level):
        if self.ipc is not None:
            return  # process already exists, recycle
        await self.io_lock.acquire()
        try:
            if self.closed.is_set():
                raise WorkerError("Attempting to create process after close")
            self.ipc = pipe_ipc.AsyncioParentComm()
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            await self.ipc.create_subprocess(
                sys.executable, "-m", "artiq.master.worker_impl",
                self.ipc.get_address(), str(log_level),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, start_new_session=True)
            asyncio.ensure_future(
                LogParser(self._get_log_source).stream_task(
                    self.ipc.process.stdout))
            asyncio.ensure_future(
                LogParser(self._get_log_source).stream_task(
                    self.ipc.process.stderr))
        finally:
            self.io_lock.release()

    async def close(self, term_timeout=2.0):
        """Interrupts any I/O with the worker process and terminates the
        worker process.

        This method should always be called by the user to clean up, even if
        build() or examine() raises an exception."""
        self.closed.set()
        await self.io_lock.acquire()
        try:
            if self.ipc is None:
                # Note the %s - self.rid can be None or a user string
                logger.debug("worker was not created (RID %s)", self.rid)
                return
            if self.ipc.process.returncode is not None:
                logger.debug("worker already terminated (RID %s)", self.rid)
                if self.ipc.process.returncode != 0:
                    logger.warning("worker finished with status code %d"
                                   " (RID %s)", self.ipc.process.returncode,
                                   self.rid)
                return
            try:
                await self._send({"action": "terminate"}, cancellable=False)
                await asyncio.wait_for(self.ipc.process.wait(), term_timeout)
                logger.debug("worker exited on request (RID %s)", self.rid)
                return
            except:
                logger.debug("worker failed to exit on request"
                             " (RID %s), ending the process", self.rid,
                             exc_info=True)
            if os.name != "nt":
                try:
                    self.ipc.process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(self.ipc.process.wait(),
                                           term_timeout)
                    logger.debug("worker terminated (RID %s)", self.rid)
                    return
                except asyncio.TimeoutError:
                    logger.warning(
                        "worker did not terminate (RID %s), killing", self.rid)
            try:
                self.ipc.process.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.ipc.process.wait(), term_timeout)
                logger.debug("worker killed (RID %s)", self.rid)
                return
            except asyncio.TimeoutError:
                logger.warning("worker refuses to die (RID %s)", self.rid)
        finally:
            self.io_lock.release()

    async def _send(self, obj, cancellable=True):
        assert self.io_lock.locked()
        line = pyon.encode(obj)
        self.ipc.write((line + "\n").encode())
        ifs = [self.ipc.drain()]
        if cancellable:
            ifs.append(self.closed.wait())
        fs = await asyncio_wait_or_cancel(
            ifs, timeout=self.send_timeout,
            return_when=asyncio.FIRST_COMPLETED)
        if all(f.cancelled() for f in fs):
            raise WorkerTimeout(
                "Timeout sending data to worker (RID {})".format(self.rid))
        for f in fs:
            if not f.cancelled() and f.done():
                f.result()  # raise any exceptions
        if cancellable and self.closed.is_set():
            raise WorkerError(
                "Data transmission to worker cancelled (RID {})".format(
                    self.rid))

    async def _recv(self, timeout):
        assert self.io_lock.locked()
        fs = await asyncio_wait_or_cancel(
            [self.ipc.readline(), self.closed.wait()],
            timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if all(f.cancelled() for f in fs):
            raise WorkerTimeout(
                "Timeout receiving data from worker (RID {})".format(self.rid))
        if self.closed.is_set():
            raise WorkerError(
                "Receiving data from worker cancelled (RID {})".format(
                    self.rid))
        line = fs[0].result()
        if not line:
            raise WorkerError(
                "Worker ended while attempting to receive data (RID {})".
                format(self.rid))
        try:
            obj = pyon.decode(line.decode())
        except:
            raise WorkerError("Worker sent invalid PYON data (RID {})".format(
                self.rid))
        return obj

    async def _handle_worker_requests(self):
        while True:
            try:
                await self.io_lock.acquire()
                try:
                    obj = await self._recv(self.watchdog_time())
                finally:
                    self.io_lock.release()
            except WorkerTimeout:
                raise WorkerWatchdogTimeout
            action = obj["action"]
            if action == "completed":
                return True
            elif action == "pause":
                return False
            elif action == "exception":
                raise WorkerInternalException
            elif action == "create_watchdog":
                func = self.create_watchdog
            elif action == "delete_watchdog":
                func = self.delete_watchdog
            elif action == "register_experiment":
                func = self.register_experiment
            else:
                func = self.handlers[action]
            try:
                data = func(*obj["args"], **obj["kwargs"])
                reply = {"status": "ok", "data": data}
            except:
                reply = {
                    "status": "failed",
                    "exception": current_exc_packed()
                }
            await self.io_lock.acquire()
            try:
                await self._send(reply)
            finally:
                self.io_lock.release()

    async def _worker_action(self, obj, timeout=None):
        if timeout is not None:
            self.watchdogs[-1] = time.monotonic() + timeout
        try:
            await self.io_lock.acquire()
            try:
                await self._send(obj)
            finally:
                self.io_lock.release()
            try:
                completed = await self._handle_worker_requests()
            except WorkerTimeout:
                raise WorkerWatchdogTimeout
        finally:
            if timeout is not None:
                del self.watchdogs[-1]
        return completed

    async def build(self, rid, pipeline_name, wd, expid, priority,
                    timeout=15.0):
        self.rid = rid
        self.filename = os.path.basename(expid["file"])
        await self._create_process(expid["log_level"])
        await self._worker_action(
            {"action": "build",
             "rid": rid,
             "pipeline_name": pipeline_name,
             "wd": wd,
             "expid": expid,
             "priority": priority},
            timeout)

    async def prepare(self):
        await self._worker_action({"action": "prepare"})

    async def run(self):
        completed = await self._worker_action({"action": "run"})
        if not completed:
            self.yield_time = time.monotonic()
        return completed

    async def resume(self, request_termination):
        stop_duration = time.monotonic() - self.yield_time
        for wid, expiry in self.watchdogs:
            self.watchdogs[wid] += stop_duration
        completed = await self._worker_action({"status": "ok",
                                               "data": request_termination})
        if not completed:
            self.yield_time = time.monotonic()
        return completed

    async def analyze(self):
        await self._worker_action({"action": "analyze"})

    async def write_results(self, timeout=15.0):
        await self._worker_action({"action": "write_results"},
                                  timeout)

    async def examine(self, rid, file, timeout=20.0):
        self.rid = rid
        self.filename = os.path.basename(file)

        await self._create_process(logging.WARNING)
        r = dict()

        def register(class_name, name, arginfo, scheduler_defaults):
            r[class_name] = {"name": name, "arginfo": arginfo, "scheduler_defaults": scheduler_defaults}
        self.register_experiment = register
        await self._worker_action({"action": "examine", "file": file},
                                  timeout)
        del self.register_experiment
        return r
