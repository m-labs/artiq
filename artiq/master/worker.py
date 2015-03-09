import sys
import asyncio
import subprocess
import signal
import traceback

from artiq.protocols import pyon


class WorkerError(Exception):
    pass


class Worker:
    def __init__(self,
                 send_timeout=0.5, start_reply_timeout=1.0, term_timeout=1.0):
        self.handlers = dict()
        self.send_timeout = send_timeout
        self.start_reply_timeout = start_reply_timeout
        self.term_timeout = term_timeout

    @asyncio.coroutine
    def _create_process(self):
        self.process = yield from asyncio.create_subprocess_exec(
            sys.executable, "-m", "artiq.master.worker_impl",
            stdout=subprocess.PIPE, stdin=subprocess.PIPE)

    @asyncio.coroutine
    def _end_process(self):
        if self.process.returncode is not None:
            return
        self.process.send_signal(signal.SIGTERM)
        try:
            yield from asyncio.wait_for(
                self.process.wait(), timeout=self.term_timeout)
        except asyncio.TimeoutError:
            self.process.send_signal(signal.SIGKILL)

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
            return None
        try:
            obj = pyon.decode(line.decode())
        except:
            raise WorkerError("Worker sent invalid PYON data")
        return obj

    @asyncio.coroutine
    def run(self, rid, run_params):
        yield from self._create_process()

        try:
            obj = {"rid": rid, "run_params": run_params}
            yield from self._send(obj, self.send_timeout)
            obj = yield from self._recv(self.start_reply_timeout)
            if obj != "ack":
                raise WorkerError("Incorrect acknowledgement")
            while True:
                obj = yield from self._recv(None)
                if obj is None:
                    if self.process.returncode != 0:
                        raise WorkerError("Worker finished with status code {}"
                                          .format(self.process.returncode))
                    break
                action = obj["action"]
                del obj["action"]
                try:
                    data = self.handlers[action](**obj)
                    reply = {"status": "ok", "data": data}
                except:
                    reply = {"status": "failed",
                             "message": traceback.format_exc()}
                yield from self._send(reply, self.send_timeout)
        finally:
            yield from self._end_process()
