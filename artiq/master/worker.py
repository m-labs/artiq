import sys
import asyncio
import subprocess
import traceback
import time

from artiq.protocols import pyon


class WorkerError(Exception):
    pass


class Worker:
    def __init__(self,
                 send_timeout=0.5, prepare_timeout=15.0, term_timeout=1.0):
        self.handlers = dict()
        self.send_timeout = send_timeout
        self.prepare_timeout = prepare_timeout
        self.term_timeout = term_timeout

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
            yield from asyncio.wait_for(
                self.process.wait(), timeout=self.term_timeout)
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
            raise WorkerError("Timeout sending data from worker")
        except:
            raise WorkerError("Failed to send data to worker")

    @asyncio.coroutine
    def _recv(self, timeout):
        try:
            line = yield from asyncio.wait_for(
                self.process.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            raise WorkerError("Timeout receiving data from worker")
        if not line:
            raise WorkerError("Worker ended while attempting to receive data")
        try:
            obj = pyon.decode(line.decode())
        except:
            raise WorkerError("Worker sent invalid PYON data")
        return obj

    @asyncio.coroutine
    def _handle_worker_requests(self, timeout):
        if timeout is None:
            end_time = None
        else:
            end_time = time.monotonic() + timeout
        while True:
            obj = yield from self._recv(None if end_time is None
                else end_time - time.monotonic())
            action = obj["action"]
            if action == "completed":
                return
            del obj["action"]
            try:
                data = self.handlers[action](**obj)
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
            yield from self._handle_worker_requests(self.prepare_timeout)
        except:
            yield from self.close()
            raise

    @asyncio.coroutine
    def run(self):
        obj = {"action": "run"}
        yield from self._send(obj, self.send_timeout)
        yield from self._handle_worker_requests(None)

    @asyncio.coroutine
    def analyze(self):
        obj = {"action": "analyze"}
        yield from self._send(obj, self.send_timeout)
        yield from self._handle_worker_requests(None)
