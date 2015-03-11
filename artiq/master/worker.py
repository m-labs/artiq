import sys
import asyncio
import subprocess
import traceback
import time

from artiq.protocols import pyon
from artiq.language.units import strip_unit
from artiq.tools import asyncio_process_wait_timeout


class WorkerTimeout(Exception):
    pass


class WorkerWatchdogTimeout(Exception):
    pass


class WorkerError(Exception):
    pass


class Worker:
    def __init__(self, handlers,
                 send_timeout=0.5, prepare_timeout=15.0, term_timeout=1.0):
        self.handlers = handlers
        self.send_timeout = send_timeout
        self.prepare_timeout = prepare_timeout
        self.term_timeout = term_timeout
        self.watchdogs = dict()  # wid -> expiration (using time.monotonic)

    def create_watchdog(self, t):
        avail = set(range(len(self.watchdogs) + 1)) \
            - set(self.watchdogs.keys())
        wid = next(iter(avail))
        self.watchdogs[wid] = time.monotonic() + strip_unit(t, "s")
        return wid

    def delete_watchdog(self, wid):
        del self.watchdogs[wid]

    def watchdog_time(self):
        if self.watchdogs:
            return min(self.watchdogs.values()) - time.monotonic()
        else:
            return None

    @asyncio.coroutine
    def _create_process(self):
        self.process = yield from asyncio.create_subprocess_exec(
            sys.executable, "-m", "artiq.master.worker_impl",
            stdout=subprocess.PIPE, stdin=subprocess.PIPE)

    @asyncio.coroutine
    def close(self):
        if self.process.returncode is not None:
            if process.returncode != 0:
                raise WorkerError("Worker finished with status code {}"
                                  .format(process.returncode))
            return
        obj = {"action": "terminate"}
        try:
            yield from self._send(obj, self.send_timeout)
        except:
            self.process.kill()
            return
        try:
            yield from asyncio_process_wait_timeout(self.process,
                                                    self.term_timeout)
        except asyncio.TimeoutError:
            self.process.kill()

    @asyncio.coroutine
    def _send(self, obj, timeout):
        line = pyon.encode(obj)
        self.process.stdin.write(line.encode())
        self.process.stdin.write("\n".encode())
        try:
            fut = self.process.stdin.drain()
            if fut is not ():  # FIXME: why does Python return this?
                yield from asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            raise WorkerTimeout("Timeout sending data from worker")
        except:
            raise WorkerError("Failed to send data to worker")

    @asyncio.coroutine
    def _recv(self, timeout):
        try:
            line = yield from asyncio.wait_for(
                self.process.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            raise WorkerTimeout("Timeout receiving data from worker")
        if not line:
            raise WorkerError("Worker ended while attempting to receive data")
        try:
            obj = pyon.decode(line.decode())
        except:
            raise WorkerError("Worker sent invalid PYON data")
        return obj

    @asyncio.coroutine
    def _handle_worker_requests(self, timeout_func):
        while True:
            obj = yield from self._recv(timeout_func())
            action = obj["action"]
            if action == "completed":
                return
            del obj["action"]
            if action == "create_watchdog":
                func = self.create_watchdog
            elif action == "delete_watchdog":
                func = self.delete_watchdog
            else:
                func = self.handlers[action]
            try:
                data = func(**obj)
                reply = {"status": "ok", "data": data}
            except:
                reply = {"status": "failed",
                         "message": traceback.format_exc()}
            yield from self._send(reply, self.send_timeout)

    @asyncio.coroutine
    def prepare(self, rid, run_params):
        yield from self._create_process()
        try:
            obj = {"action": "prepare", "rid": rid, "run_params": run_params}
            yield from self._send(obj, self.send_timeout)
            end_time = time.monotonic() + self.prepare_timeout
            yield from self._handle_worker_requests(
                lambda: end_time - time.monotonic())
        except:
            yield from self.close()
            raise

    @asyncio.coroutine
    def _run_analyze(self, action):
        obj = {"action": action}
        yield from self._send(obj, self.send_timeout)
        try:
            yield from self._handle_worker_requests(self.watchdog_time)
        except WorkerTimeout:
            raise WorkerWatchdogTimeout

    @asyncio.coroutine
    def run(self):
        yield from self._run_analyze("run")

    @asyncio.coroutine
    def analyze(self):
        yield from self._run_analyze("analyze")
