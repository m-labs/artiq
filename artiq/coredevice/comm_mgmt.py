from enum import Enum
import logging
import socket
import struct


logger = logging.getLogger(__name__)


class Request(Enum):
    GetLog = 1
    ClearLog = 2
    SetLogFilter = 3
    SetUartLogFilter = 6

    Hotswap = 4
    Reboot = 5


class Reply(Enum):
    Success = 1

    LogContent = 2

    RebootImminent = 3


class LogLevel(Enum):
    OFF = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4
    TRACE = 5


def initialize_connection(host, port):
    sock = socket.create_connection((host, port), 5.0)
    sock.settimeout(None)
    logger.debug("connected to host %s on port %d", host, port)
    return sock


class CommMgmt:
    def __init__(self, dmgr, host, port=1380):
        self.host = host
        self.port = port

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = initialize_connection(self.host, self.port)
        self.socket.sendall(b"ARTIQ management\n")

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket
        logger.debug("disconnected")

    # Protocol elements

    def _write(self, data):
        self.socket.sendall(data)

    def _write_header(self, ty):
        self.open()

        logger.debug("sending message: type=%r", ty)
        self._write(struct.pack("B", ty.value))

    def _write_int8(self, value):
        self._write(struct.pack("B", value))

    def _write_int32(self, value):
        self._write(struct.pack(">l", value))

    def _write_bytes(self, value):
        self._write_int32(len(value))
        self._write(value)

    def _read(self, length):
        r = bytes()
        while len(r) < length:
            rn = self.socket.recv(min(8192, length - len(r)))
            if not rn:
                raise ConnectionResetError("Connection closed")
            r += rn
        return r

    def _read_header(self):
        ty = Reply(*struct.unpack("B", self._read(1)))
        logger.debug("receiving message: type=%r", ty)

        return ty

    def _read_expect(self, ty):
        if self._read_header() != ty:
            raise IOError("Incorrect reply from device: {} (expected {})".
                          format(self._read_type, ty))

    def _read_int32(self):
        (value, ) = struct.unpack(">l", self._read(4))
        return value

    def _read_bytes(self):
        return self._read(self._read_int32())

    def _read_string(self):
        return self._read_bytes().decode("utf-8")

    # External API

    def get_log(self):
        self._write_header(Request.GetLog)
        self._read_expect(Reply.LogContent)
        return self._read_string()

    def clear_log(self):
        self._write_header(Request.ClearLog)
        self._read_expect(Reply.Success)

    def set_log_level(self, level):
        if level not in LogLevel.__members__:
            raise ValueError("invalid log level {}".format(level))

        self._write_header(Request.SetLogFilter)
        self._write_int8(getattr(LogLevel, level).value)
        self._read_expect(Reply.Success)

    def set_uart_log_level(self, level):
        if level not in LogLevel.__members__:
            raise ValueError("invalid log level {}".format(level))

        self._write_header(Request.SetUartLogFilter)
        self._write_int8(getattr(LogLevel, level).value)
        self._read_expect(Reply.Success)

    def hotswap(self, firmware):
        self._write_header(Request.Hotswap)
        self._write_bytes(firmware)
        self._read_expect(Reply.RebootImminent)

    def reboot(self):
        self._write_header(Request.Reboot)
        self._read_expect(Reply.RebootImminent)
