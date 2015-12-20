import asyncio
import logging

from artiq.protocols.asyncio_server import AsyncioServer
from artiq.tools import TaskObject


logger = logging.getLogger(__name__)
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
                linesplit = line.split(":", 3)
                if len(linesplit) != 4:
                    logger.warning("received improperly formatted message, "
                                   "dropping connection")
                    return
                source, level, name, message = linesplit
                try:
                    level = int(level)
                except:
                    logger.warning("received improperly formatted level, "
                                   "dropping connection")
                    return
                log_with_name(name, level, message,
                              extra={"source": source})
        finally:
            writer.close()


class SourceFilter:
    def __init__(self, local_level, local_source):
        self.local_level = local_level
        self.local_source = local_source

    def filter(self, record):
        if not hasattr(record, "source"):
            record.source = self.local_source
        if record.source == self.local_source:
            return record.levelno >= self.local_level
        else:
            # log messages that are forwarded from a source have already
            # been filtered, and may have a level below the local level.
            return True


class LogForwarder(logging.Handler, TaskObject):
    def __init__(self, host, port, reconnect_timer=5.0, queue_size=1000,
                 **kwargs):
        logging.Handler.__init__(self, **kwargs)
        self.host = host
        self.port = port
        self.setFormatter(logging.Formatter(
            "%(name)s:%(message)s"))
        self._queue = asyncio.Queue(queue_size)
        self.reconnect_timer = reconnect_timer

    def emit(self, record):
        message = self.format(record)
        for part in message.split("\n"):
            part = "{}:{}:{}".format(record.source, record.levelno, part)
            try:
                self._queue.put_nowait(part)
            except asyncio.QueueFull:
                break

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
