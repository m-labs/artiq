import struct
import logging
import socket
import sys
import traceback
import numpy
from enum import Enum
from fractions import Fraction
from collections import namedtuple

from artiq.coredevice import exceptions
from artiq import __version__ as software_version


logger = logging.getLogger(__name__)


class _H2DMsgType(Enum):
    LOG_REQUEST = 1
    LOG_CLEAR = 2
    LOG_FILTER = 13

    SYSTEM_INFO_REQUEST = 3
    SWITCH_CLOCK = 4

    LOAD_KERNEL = 5
    RUN_KERNEL = 6

    RPC_REPLY = 7
    RPC_EXCEPTION = 8

    FLASH_READ_REQUEST = 9
    FLASH_WRITE_REQUEST = 10
    FLASH_ERASE_REQUEST = 11
    FLASH_REMOVE_REQUEST = 12

    HOTSWAP = 14


class _D2HMsgType(Enum):
    LOG_REPLY = 1

    SYSTEM_INFO_REPLY = 2
    CLOCK_SWITCH_COMPLETED = 3
    CLOCK_SWITCH_FAILED = 4

    LOAD_COMPLETED = 5
    LOAD_FAILED = 6

    KERNEL_FINISHED = 7
    KERNEL_STARTUP_FAILED = 8
    KERNEL_EXCEPTION = 9

    RPC_REQUEST = 10

    FLASH_READ_REPLY = 11
    FLASH_OK_REPLY = 12
    FLASH_ERROR_REPLY = 13

    WATCHDOG_EXPIRED = 14
    CLOCK_FAILURE = 15

    HOTSWAP_IMMINENT = 16


class _LogLevel(Enum):
    OFF = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4
    TRACE = 5


class UnsupportedDevice(Exception):
    pass

class LoadError(Exception):
    pass

class RPCReturnValueError(ValueError):
    pass


RPCKeyword = namedtuple('RPCKeyword', ['name', 'value'])


def set_keepalive(sock, after_idle, interval, max_fails):
    if sys.platform.startswith("linux"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)
    elif sys.platform.startswith("win") or sys.platform.startswith("cygwin"):
        # setting max_fails is not supported, typically ends up being 5 or 10
        # depending on Windows version
        sock.ioctl(socket.SIO_KEEPALIVE_VALS,
                   (1, after_idle*1000, interval*1000))
    else:
        logger.warning("TCP keepalive not supported on platform '%s', ignored",
                       sys.platform)


def initialize_connection(host, port):
    sock = socket.create_connection((host, port), 5.0)
    sock.settimeout(None)
    set_keepalive(sock, 3, 2, 3)
    logger.debug("connected to host %s on port %d", host, port)
    return sock


class CommKernelDummy:
    def __init__(self):
        pass

    def switch_clock(self, external):
        pass

    def load(self, kernel_library):
        pass

    def run(self):
        pass

    def serve(self, embedding_map, symbolizer, demangler):
        pass

    def check_system_info(self):
        pass

    def get_log(self):
        return ""

    def clear_log(self):
        pass


class CommKernel:
    def __init__(self, host, port=1381):
        self._read_type = None
        self.host = host
        self.port = port

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = initialize_connection(self.host, self.port)
        self.socket.sendall(b"ARTIQ coredev\n")

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket
        logger.debug("disconnected")

    def read(self, length):
        r = bytes()
        while len(r) < length:
            rn = self.socket.recv(min(8192, length - len(r)))
            if not rn:
                raise ConnectionResetError("Connection closed")
            r += rn
        return r

    def write(self, data):
        self.socket.sendall(data)

    #
    # Reader interface
    #

    def _read_header(self):
        self.open()

        # Wait for a synchronization sequence, 5a 5a 5a 5a.
        sync_count = 0
        while sync_count < 4:
            (sync_byte, ) = struct.unpack("B", self.read(1))
            if sync_byte == 0x5a:
                sync_count += 1
            else:
                sync_count = 0

        # Read message header.
        (raw_type, ) = struct.unpack("B", self.read(1))
        self._read_type = _D2HMsgType(raw_type)

        logger.debug("receiving message: type=%r",
                     self._read_type)

    def _read_expect(self, ty):
        if self._read_type != ty:
            raise IOError("Incorrect reply from device: {} (expected {})".
                          format(self._read_type, ty))

    def _read_empty(self, ty):
        self._read_header()
        self._read_expect(ty)

    def _read_chunk(self, length):
        return self.read(length)

    def _read_int8(self):
        (value, ) = struct.unpack("B",  self._read_chunk(1))
        return value

    def _read_int32(self):
        (value, ) = struct.unpack(">l", self._read_chunk(4))
        return value

    def _read_int64(self):
        (value, ) = struct.unpack(">q", self._read_chunk(8))
        return value

    def _read_float64(self):
        (value, ) = struct.unpack(">d", self._read_chunk(8))
        return value

    def _read_bool(self):
        return True if self._read_int8() else False

    def _read_bytes(self):
        return self._read_chunk(self._read_int32())

    def _read_string(self):
        return self._read_bytes().decode("utf-8")

    #
    # Writer interface
    #

    def _write_header(self, ty):
        self.open()

        logger.debug("sending message: type=%r", ty)

        # Write synchronization sequence and header.
        self.write(struct.pack(">lB", 0x5a5a5a5a, ty.value))

    def _write_empty(self, ty):
        self._write_header(ty)

    def _write_chunk(self, chunk):
        self.write(chunk)

    def _write_int8(self, value):
        self.write(struct.pack("B", value))

    def _write_int32(self, value):
        self.write(struct.pack(">l", value))

    def _write_int64(self, value):
        self.write(struct.pack(">q", value))

    def _write_float64(self, value):
        self.write(struct.pack(">d", value))

    def _write_bool(self, value):
        self.write(struct.pack("B", value))

    def _write_bytes(self, value):
        self._write_int32(len(value))
        self.write(value)

    def _write_string(self, value):
        self._write_bytes(value.encode("utf-8"))

    #
    # Exported APIs
    #

    def reset_session(self):
        self.write(struct.pack(">ll", 0x5a5a5a5a, 0))

    def check_system_info(self):
        self._write_empty(_H2DMsgType.SYSTEM_INFO_REQUEST)

        self._read_header()
        self._read_expect(_D2HMsgType.SYSTEM_INFO_REPLY)
        runtime_id = self._read_chunk(4)
        if runtime_id != b"AROR":
            raise UnsupportedDevice("Unsupported runtime ID: {}"
                                    .format(runtime_id))

        gateware_version = self._read_string()
        if gateware_version != software_version:
            logger.warning("Mismatch between gateware (%s) "
                           "and software (%s) versions",
                           gateware_version, software_version)

        finished_cleanly = self._read_bool()
        if not finished_cleanly:
            logger.warning("Previous kernel did not cleanly finish")

    def switch_clock(self, external):
        self._write_header(_H2DMsgType.SWITCH_CLOCK)
        self._write_int8(external)

        self._read_empty(_D2HMsgType.CLOCK_SWITCH_COMPLETED)

    def flash_storage_read(self, key):
        self._write_header(_H2DMsgType.FLASH_READ_REQUEST)
        self._write_string(key)

        self._read_header()
        self._read_expect(_D2HMsgType.FLASH_READ_REPLY)
        return self._read_string()

    def flash_storage_write(self, key, value):
        self._write_header(_H2DMsgType.FLASH_WRITE_REQUEST)
        self._write_string(key)
        self._write_bytes(value)

        self._read_header()
        if self._read_type == _D2HMsgType.FLASH_ERROR_REPLY:
            raise IOError("Flash storage is full")
        else:
            self._read_expect(_D2HMsgType.FLASH_OK_REPLY)

    def flash_storage_erase(self):
        self._write_empty(_H2DMsgType.FLASH_ERASE_REQUEST)

        self._read_empty(_D2HMsgType.FLASH_OK_REPLY)

    def flash_storage_remove(self, key):
        self._write_header(_H2DMsgType.FLASH_REMOVE_REQUEST)
        self._write_string(key)

        self._read_empty(_D2HMsgType.FLASH_OK_REPLY)

    def load(self, kernel_library):
        self._write_header(_H2DMsgType.LOAD_KERNEL)
        self._write_bytes(kernel_library)

        self._read_header()
        if self._read_type == _D2HMsgType.LOAD_FAILED:
            raise LoadError(self._read_string())
        else:
            self._read_expect(_D2HMsgType.LOAD_COMPLETED)

    def run(self):
        self._write_empty(_H2DMsgType.RUN_KERNEL)
        logger.debug("running kernel")

    _rpc_sentinel = object()

    # See session.c:{send,receive}_rpc_value and llvm_ir_generator.py:_rpc_tag.
    def _receive_rpc_value(self, embedding_map):
        tag = chr(self._read_int8())
        if tag == "\x00":
            return self._rpc_sentinel
        elif tag == "t":
            length = self._read_int8()
            return tuple(self._receive_rpc_value(embedding_map) for _ in range(length))
        elif tag == "n":
            return None
        elif tag == "b":
            return bool(self._read_int8())
        elif tag == "i":
            return numpy.int32(self._read_int32())
        elif tag == "I":
            return numpy.int64(self._read_int64())
        elif tag == "f":
            return self._read_float64()
        elif tag == "F":
            numerator   = self._read_int64()
            denominator = self._read_int64()
            return Fraction(numerator, denominator)
        elif tag == "s":
            return self._read_string()
        elif tag == "B":
            return self._read_bytes()
        elif tag == "A":
            return self._read_bytes()
        elif tag == "l":
            length = self._read_int32()
            return [self._receive_rpc_value(embedding_map) for _ in range(length)]
        elif tag == "a":
            length = self._read_int32()
            return numpy.array([self._receive_rpc_value(embedding_map) for _ in range(length)])
        elif tag == "r":
            start = self._receive_rpc_value(embedding_map)
            stop  = self._receive_rpc_value(embedding_map)
            step  = self._receive_rpc_value(embedding_map)
            return range(start, stop, step)
        elif tag == "k":
            name  = self._read_string()
            value = self._receive_rpc_value(embedding_map)
            return RPCKeyword(name, value)
        elif tag == "O":
            return embedding_map.retrieve_object(self._read_int32())
        else:
            raise IOError("Unknown RPC value tag: {}".format(repr(tag)))

    def _receive_rpc_args(self, embedding_map):
        args, kwargs = [], {}
        while True:
            value = self._receive_rpc_value(embedding_map)
            if value is self._rpc_sentinel:
                return args, kwargs
            elif isinstance(value, RPCKeyword):
                kwargs[value.name] = value.value
            else:
                args.append(value)

    def _skip_rpc_value(self, tags):
        tag = tags.pop(0)
        if tag == "t":
            length = tags.pop(0)
            for _ in range(length):
                self._skip_rpc_value(tags)
        elif tag == "l":
            self._skip_rpc_value(tags)
        elif tag == "r":
            self._skip_rpc_value(tags)
        else:
            pass

    def _send_rpc_value(self, tags, value, root, function):
        def check(cond, expected):
            if not cond:
                raise RPCReturnValueError(
                    "type mismatch: cannot serialize {value} as {type}"
                    " ({function} has returned {root})".format(
                        value=repr(value), type=expected(),
                        function=function, root=root))

        tag = chr(tags.pop(0))
        if tag == "t":
            length = tags.pop(0)
            check(isinstance(value, tuple) and length == len(value),
                  lambda: "tuple of {}".format(length))
            for elt in value:
                self._send_rpc_value(tags, elt, root, function)
        elif tag == "n":
            check(value is None,
                  lambda: "None")
        elif tag == "b":
            check(isinstance(value, bool),
                  lambda: "bool")
            self._write_int8(value)
        elif tag == "i":
            check(isinstance(value, (int, numpy.int32)) and
                  (-2**31 < value < 2**31-1),
                  lambda: "32-bit int")
            self._write_int32(value)
        elif tag == "I":
            check(isinstance(value, (int, numpy.int32, numpy.int64)) and
                  (-2**63 < value < 2**63-1),
                  lambda: "64-bit int")
            self._write_int64(value)
        elif tag == "f":
            check(isinstance(value, float),
                  lambda: "float")
            self._write_float64(value)
        elif tag == "F":
            check(isinstance(value, Fraction) and
                    (-2**63 < value.numerator < 2**63-1) and
                    (-2**63 < value.denominator < 2**63-1),
                  lambda: "64-bit Fraction")
            self._write_int64(value.numerator)
            self._write_int64(value.denominator)
        elif tag == "s":
            check(isinstance(value, str) and "\x00" not in value,
                  lambda: "str")
            self._write_string(value)
        elif tag == "B":
            check(isinstance(value, bytes),
                  lambda: "bytes")
            self._write_bytes(value)
        elif tag == "A":
            check(isinstance(value, bytearray),
                  lambda: "bytearray")
            self._write_bytes(value)
        elif tag == "l":
            check(isinstance(value, list),
                  lambda: "list")
            self._write_int32(len(value))
            for elt in value:
                tags_copy = bytearray(tags)
                self._send_rpc_value(tags_copy, elt, root, function)
            self._skip_rpc_value(tags)
        elif tag == "r":
            check(isinstance(value, range),
                  lambda: "range")
            tags_copy = bytearray(tags)
            self._send_rpc_value(tags_copy, value.start, root, function)
            tags_copy = bytearray(tags)
            self._send_rpc_value(tags_copy, value.stop, root, function)
            tags_copy = bytearray(tags)
            self._send_rpc_value(tags_copy, value.step, root, function)
            tags = tags_copy
        else:
            raise IOError("Unknown RPC value tag: {}".format(repr(tag)))

    def _truncate_message(self, msg, limit=4096):
        if len(msg) > limit:
            return msg[0:limit] + "... (truncated)"
        else:
            return msg

    def _serve_rpc(self, embedding_map):
        async        = self._read_bool()
        service_id   = self._read_int32()
        args, kwargs = self._receive_rpc_args(embedding_map)
        return_tags  = self._read_bytes()

        if service_id is 0:
            service  = lambda obj, attr, value: setattr(obj, attr, value)
        else:
            service  = embedding_map.retrieve_object(service_id)
        logger.debug("rpc service: [%d]%r%s %r %r -> %s", service_id, service,
                     (" (async)" if async else ""), args, kwargs, return_tags)

        if async:
            service(*args, **kwargs)
            return

        try:
            result = service(*args, **kwargs)
            logger.debug("rpc service: %d %r %r = %r", service_id, args, kwargs, result)

            self._write_header(_H2DMsgType.RPC_REPLY)
            self._write_bytes(return_tags)
            self._send_rpc_value(bytearray(return_tags), result, result, service)
        except RPCReturnValueError as exn:
            raise
        except Exception as exn:
            logger.debug("rpc service: %d %r %r ! %r", service_id, args, kwargs, exn)

            self._write_header(_H2DMsgType.RPC_EXCEPTION)

            if hasattr(exn, "artiq_core_exception"):
                exn = exn.artiq_core_exception
                self._write_string(exn.name)
                self._write_string(self._truncate_message(exn.message))
                for index in range(3):
                    self._write_int64(exn.param[index])

                filename, line, column, function = exn.traceback[-1]
                self._write_string(filename)
                self._write_int32(line)
                self._write_int32(column)
                self._write_string(function)
            else:
                exn_type = type(exn)
                if exn_type in (ZeroDivisionError, ValueError, IndexError) or \
                        hasattr(exn, "artiq_builtin"):
                    self._write_string("0:{}".format(exn_type.__name__))
                else:
                    exn_id = embedding_map.store_object(exn_type)
                    self._write_string("{}:{}.{}".format(exn_id,
                                                         exn_type.__module__,
                                                         exn_type.__qualname__))
                self._write_string(self._truncate_message(str(exn)))
                for index in range(3):
                    self._write_int64(0)

                tb = traceback.extract_tb(exn.__traceback__, 2)
                if len(tb) == 2:
                    (_, (filename, line, function, _), ) = tb
                elif len(tb) == 1:
                    ((filename, line, function, _), ) = tb
                else:
                    assert False
                self._write_string(filename)
                self._write_int32(line)
                self._write_int32(-1) # column not known
                self._write_string(function)

    def _serve_exception(self, embedding_map, symbolizer, demangler):
        name      = self._read_string()
        message   = self._read_string()
        params    = [self._read_int64() for _ in range(3)]

        filename  = self._read_string()
        line      = self._read_int32()
        column    = self._read_int32()
        function  = self._read_string()

        backtrace = [self._read_int32() for _ in range(self._read_int32())]

        traceback = list(reversed(symbolizer(backtrace))) + \
                    [(filename, line, column, *demangler([function]), None)]
        core_exn = exceptions.CoreException(name, message, params, traceback)

        if core_exn.id == 0:
            python_exn_type = getattr(exceptions, core_exn.name.split('.')[-1])
        else:
            python_exn_type = embedding_map.retrieve_object(core_exn.id)

        python_exn = python_exn_type(message.format(*params))
        python_exn.artiq_core_exception = core_exn
        raise python_exn

    def serve(self, embedding_map, symbolizer, demangler):
        while True:
            self._read_header()
            if self._read_type == _D2HMsgType.RPC_REQUEST:
                self._serve_rpc(embedding_map)
            elif self._read_type == _D2HMsgType.KERNEL_EXCEPTION:
                self._serve_exception(embedding_map, symbolizer, demangler)
            elif self._read_type == _D2HMsgType.WATCHDOG_EXPIRED:
                raise exceptions.WatchdogExpired
            elif self._read_type == _D2HMsgType.CLOCK_FAILURE:
                raise exceptions.ClockFailure
            else:
                self._read_expect(_D2HMsgType.KERNEL_FINISHED)
                return
