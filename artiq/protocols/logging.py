import asyncio
import logging

from artiq.protocols.asyncio_server import AsyncioServer
from artiq.tools import TaskObject


_fwd_logger = logging.getLogger("fwd")


def log_with_name(name, *args, **kwargs):
    _fwd_logger.name = name
    _fwd_logger.log(*args, **kwargs)


_name_to_level = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def parse_log_message(msg):
    for name, level in _name_to_level.items():
        if msg.startswith(name + ":"):
            remainder = msg[len(name) + 1:]
            try:
                idx = remainder.index(":")
            except:
                continue
            return level, remainder[:idx], remainder[idx+1:]
    return logging.INFO, "print", msg


_init_string = b"ARTIQ logging\n"


class Server(AsyncioServer):
    """Remote logging TCP server.

    Takes one log entry per line, in the format:
        source:levelno:name:message
    """
    async def _handle_connection_cr(self, reader, writer):
        try:
            line = await reader.readline()
            if line != _init_string:
                return

            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    line = line.decode()
                except:
                    return
                line = line[:-1]
                linesplit = line.split(":", 4)
                if len(linesplit) != 4:
                    return
                source, level, name, message = linesplit
                try:
                    level = int(level)
                except:
                    return
                log_with_name(name, level, message,
                              extra={"source": source})
        finally:
            writer.close()


class LogForwarder(logging.Handler, TaskObject):
    def __init__(self, host, port, reconnect_timer=5.0, queue_size=1000,
                 **kwargs):
        logging.Handler.__init__(self, **kwargs)
        self.host = host
        self.port = port
        self.setFormatter(logging.Formatter(
            "%(source)s:%(levelno)d:%(name)s:%(message)s"))
        self._queue = asyncio.Queue(queue_size)
        self.reconnect_timer = reconnect_timer

    def emit(self, record):
        message = self.format(record)
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            pass

    async def _do(self):
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host,
                                                               self.port)
                writer.write(_init_string)
                while True:
                    message = await self._queue.get() + "\n"
                    writer.write(message.encode())
                    await writer.drain()
            except asyncio.CancelledError:
                return
            except:
                await asyncio.sleep(self.reconnect_timer)
            finally:
                writer.close()
