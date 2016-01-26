import asyncio
import logging
import re

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
    lr = "|".join(_name_to_level.keys())
    m = re.fullmatch('('+lr+')(<\d+>)?:([^:]*):(.*)', msg)
    if m is None:
        return 0, logging.INFO, "print", msg
    level = _name_to_level[m.group(1)]
    if m.group(2):
        multiline = int(m.group(2)[1:-1]) - 1
    else:
        multiline = 0
    name = m.group(3)
    message = m.group(4)
    return multiline, level, name, message


class LogParser:
    def __init__(self, source_cb):
        self.source_cb = source_cb
        self.multiline_count = 0
        self.multiline_level = None
        self.multiline_name = None
        self.multiline_message = None

    def line_input(self, msg):
        if self.multiline_count:
            self.multiline_message += "\n" + msg
            self.multiline_count -= 1
            if not self.multiline_count:
                log_with_name(
                    self.multiline_name,
                    self.multiline_level,
                    self.multiline_message,
                    extra={"source": self.source_cb()})
                self.multiline_level = None
                self.multiline_name = None
                self.multiline_message = None
        else:
            multiline, level, name, message = parse_log_message(msg)
            if multiline:
                self.multiline_count = multiline
                self.multiline_level = level
                self.multiline_name = name
                self.multiline_message = message
            else:
                log_with_name(name, level, message,
                              extra={"source": self.source_cb()})

    async def stream_task(self, stream):
        while True:
            try:
                entry = (await stream.readline())
                if not entry:
                    break
                self.line_input(entry[:-1].decode())
            except:
                logger.debug("exception in log forwarding", exc_info=True)
                break
        logger.debug("stopped log forwarding of stream %s of %s",
            stream, self.source_cb())


class MultilineFormatter(logging.Formatter):
    def __init__(self):
        logging.Formatter.__init__(
            self, "%(levelname)s:%(name)s:%(message)s")

    def format(self, record):
        r = logging.Formatter.format(self, record)
        linebreaks = r.count("\n")
        if linebreaks:
            i = r.index(":")
            r = r[:i] + "<" + str(linebreaks + 1) + ">" + r[i:]
        return r


def multiline_log_config(level):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(MultilineFormatter())
    root_logger.addHandler(handler)


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
