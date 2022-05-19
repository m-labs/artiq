from enum import Enum
import logging
import struct

from sipyco.keepalive import create_connection

logger = logging.getLogger(__name__)


class Request(Enum):
    GetLog = 1
    ClearLog = 2
    PullLog = 7
    SetLogFilter = 3
    SetUartLogFilter = 6

    ConfigRead = 12
    ConfigWrite = 13
    ConfigRemove = 14
    ConfigErase = 15

    Reboot = 5

    DebugAllocator = 8


class Reply(Enum):
    Success = 1
    Error = 6
    Unavailable = 4

    LogContent = 2

    ConfigData = 7

    RebootImminent = 3


class LogLevel(Enum):
    OFF = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4
    TRACE = 5


class CommMgmt:
    def __init__(self, host, port=1380):
        self.host = host
        self.port = port

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = create_connection(self.host, self.port)
        self.socket.sendall(b"ARTIQ management\n")
        endian = self._read(1)
        if endian == b"e":
            self.endian = "<"
        elif endian == b"E":
            self.endian = ">"
        else:
            raise IOError("Incorrect reply from device: expected e/E.")

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
        self._write(struct.pack(self.endian + "l", value))

    def _write_bytes(self, value):
        self._write_int32(len(value))
        self._write(value)

    def _write_string(self, value):
        self._write_bytes(value.encode("utf-8"))

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
        header = self._read_header()
        if header != ty:
            raise IOError("Incorrect reply from device: {} (expected {})".
                          format(header, ty))

    def _read_int32(self):
        (value, ) = struct.unpack(self.endian + "l", self._read(4))
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

    def pull_log(self):
        self._write_header(Request.PullLog)
        self._read_expect(Reply.LogContent)
        return self._read_string()

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

    def config_read(self, key):
        self._write_header(Request.ConfigRead)
        self._write_string(key)
        ty = self._read_header()
        if ty == Reply.Error:
            raise IOError("Device failed to read config. The key may not exist.")
        elif ty != Reply.ConfigData:
            raise IOError("Incorrect reply from device: {} (expected {})".
                          format(ty, Reply.ConfigData))
        return self._read_string()

    def config_write(self, key, value):
        self._write_header(Request.ConfigWrite)
        self._write_string(key)
        self._write_bytes(value)
        ty = self._read_header()
        if ty == Reply.Error:
            raise IOError("Device failed to write config. More information may be available in the log.")
        elif ty != Reply.Success:
            raise IOError("Incorrect reply from device: {} (expected {})".
                          format(ty, Reply.Success))

    def config_remove(self, key):
        self._write_header(Request.ConfigRemove)
        self._write_string(key)
        self._read_expect(Reply.Success)

    def config_erase(self):
        self._write_header(Request.ConfigErase)
        self._read_expect(Reply.Success)

    def reboot(self):
        self._write_header(Request.Reboot)
        self._read_expect(Reply.RebootImminent)

    def debug_allocator(self):
        self._write_header(Request.DebugAllocator)
