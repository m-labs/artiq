import asyncio

from artiq.monkey_patches import *
from artiq.protocols import pyon
from artiq.protocols.asyncio_server import AsyncioServer


_init_string = b"ARTIQ broadcast\n"


class Receiver:
    def __init__(self, name, notify_cb, disconnect_cb=None):
        self.name = name
        if not isinstance(notify_cb, list):
            notify_cb = [notify_cb]
        self.notify_cbs = notify_cb
        self.disconnect_cb = disconnect_cb

    async def connect(self, host, port):
        self.reader, self.writer = \
            await asyncio.open_connection(host, port, limit=100*1024*1024)
        try:
            self.writer.write(_init_string)
            self.writer.write((self.name + "\n").encode())
            self.receive_task = asyncio.ensure_future(self._receive_cr())
        except:
            self.writer.close()
            del self.reader
            del self.writer
            raise

    async def close(self):
        self.disconnect_cb = None
        try:
            self.receive_task.cancel()
            try:
                await asyncio.wait_for(self.receive_task, None)
            except asyncio.CancelledError:
                pass
        finally:
            self.writer.close()
            del self.reader
            del self.writer

    async def _receive_cr(self):
        try:
            target = None
            while True:
                line = await self.reader.readline()
                if not line:
                    return
                obj = pyon.decode(line.decode())

                for notify_cb in self.notify_cbs:
                    notify_cb(obj)
        finally:
            if self.disconnect_cb is not None:
                self.disconnect_cb()


class Broadcaster(AsyncioServer):
    def __init__(self, queue_limit=1024):
        AsyncioServer.__init__(self)
        self._queue_limit = queue_limit
        self._recipients = dict()

    async def _handle_connection_cr(self, reader, writer):
        try:
            line = await reader.readline()
            if line != _init_string:
                return

            line = await reader.readline()
            if not line:
                return
            name = line.decode()[:-1]

            queue = asyncio.Queue(self._queue_limit)
            if name in self._recipients:
                self._recipients[name].add(queue)
            else:
                self._recipients[name] = {queue}
            try:
                while True:
                    line = await queue.get()
                    writer.write(line)
                    # raise exception on connection error
                    await writer.drain()
            finally:
                self._recipients[name].remove(queue)
                if not self._recipients[name]:
                    del self._recipients[name]
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            # receivers disconnecting are a normal occurence
            pass
        finally:
            writer.close()

    def broadcast(self, name, obj):
        if name in self._recipients:
            line = pyon.encode(obj) + "\n"
            line = line.encode()
            for recipient in self._recipients[name]:
                try:
                    recipient.put_nowait(line)
                except asyncio.QueueFull:
                    # do not log: log messages may be sent back to us
                    # as broadcasts, and cause infinite recursion.
                    pass
