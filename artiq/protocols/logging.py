import asyncio
import logging

from artiq.protocols.asyncio_server import AsyncioServer


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
                source, levelname, name, message = linesplit
                try:
                    level = _name_to_level[levelname]
                except KeyError:
                    return
                log_with_name(name, level, message,
                              extra={"source": source})
        finally:
            writer.close()
