import struct
import logging
import traceback
from enum import Enum
from fractions import Fraction

from artiq.language import core as core_language
from artiq.coredevice import exceptions
from artiq import __version__ as software_version


logger = logging.getLogger(__name__)


class _H2DMsgType(Enum):
    LOG_REQUEST = 1
    LOG_CLEAR = 2

    IDENT_REQUEST = 3
    SWITCH_CLOCK = 4

    LOAD_LIBRARY = 5
    RUN_KERNEL = 6

    RPC_REPLY = 7
    RPC_EXCEPTION = 8

    FLASH_READ_REQUEST = 9
    FLASH_WRITE_REQUEST = 10
    FLASH_ERASE_REQUEST = 11
    FLASH_REMOVE_REQUEST = 12


class _D2HMsgType(Enum):
    LOG_REPLY = 1

    IDENT_REPLY = 2
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


class UnsupportedDevice(Exception):
    pass

class RPCReturnValueError(ValueError):
    pass


class CommGeneric:
    def __init__(self):
        self._read_type = self._write_type = None
        self._read_length = 0
        self._write_buffer = []

    def open(self):
        """Opens the communication channel.
        Must do nothing if already opened."""
        raise NotImplementedError

    def close(self):
        """Closes the communication channel.
        Must do nothing if already closed."""
        raise NotImplementedError

    def read(self, length):
        """Reads exactly length bytes from the communication channel.
        The channel is assumed to be opened."""
        raise NotImplementedError

    def write(self, data):
        """Writes exactly length bytes to the communication channel.
        The channel is assumed to be opened."""
        raise NotImplementedError

    #
    # Reader interface
    #

    def _read_header(self):
        self.open()

        if self._read_length > 0:
            raise IOError("Read underrun ({} bytes remaining)".
                          format(self._read_length))

        # Wait for a synchronization sequence, 5a 5a 5a 5a.
        sync_count = 0
        while sync_count < 4:
            (sync_byte, ) = struct.unpack("B", self.read(1))
            if sync_byte == 0x5a:
                sync_count += 1
            else:
                sync_count = 0

        # Read message header.
        (self._read_length, ) = struct.unpack(">l", self.read(4))
        if not self._read_length:  # inband connection close
            raise OSError("Connection closed")

        (raw_type, ) = struct.unpack("B", self.read(1))
        self._read_type = _D2HMsgType(raw_type)

        if self._read_length < 9:
            raise IOError("Read overrun in message header ({} remaining)".
                          format(self._read_length))
        self._read_length -= 9

        logger.debug("receiving message: type=%r length=%d",
                     self._read_type, self._read_length)

    def _read_expect(self, ty):
        if self._read_type != ty:
            raise IOError("Incorrect reply from device: {} (expected {})".
                          format(self._read_type, ty))

    def _read_empty(self, ty):
        self._read_header()
        self._read_expect(ty)

    def _read_chunk(self, length):
        if self._read_length < length:
            raise IOError("Read overrun while trying to read {} bytes ({} remaining)"
                          " in packet {}".
                          format(length, self._read_length, self._read_type))

        self._read_length -= length
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

    def _read_bytes(self):
        return self._read_chunk(self._read_int32())

    def _read_string(self):
        return self._read_bytes()[:-1].decode('utf-8')

    #
    # Writer interface
    #

    def _write_header(self, ty):
        self.open()

        logger.debug("preparing to send message: type=%r", ty)
        self._write_type   = ty
        self._write_buffer = []

    def _write_flush(self):
        # Calculate message size.
        length = sum([len(chunk) for chunk in self._write_buffer])
        logger.debug("sending message: type=%r length=%d", self._write_type, length)

        # Write synchronization sequence, header and body.
        self.write(struct.pack(">llB", 0x5a5a5a5a,
                                       9 + length, self._write_type.value))
        for chunk in self._write_buffer:
            self.write(chunk)

    def _write_empty(self, ty):
        self._write_header(ty)
        self._write_flush()

    def _write_chunk(self, chunk):
        self._write_buffer.append(chunk)

    def _write_int8(self, value):
        self._write_buffer.append(struct.pack("B", value))

    def _write_int32(self, value):
        self._write_buffer.append(struct.pack(">l", value))

    def _write_int64(self, value):
        self._write_buffer.append(struct.pack(">q", value))

    def _write_float64(self, value):
        self._write_buffer.append(struct.pack(">d", value))

    def _write_bytes(self, value):
        self._write_int32(len(value))
        self._write_buffer.append(value)

    def _write_string(self, value):
        self._write_bytes(value.encode("utf-8") + b"\0")

    #
    # Exported APIs
    #

    def reset_session(self):
        self.write(struct.pack(">ll", 0x5a5a5a5a, 0))

    def check_ident(self):
        self._write_empty(_H2DMsgType.IDENT_REQUEST)

        self._read_header()
        self._read_expect(_D2HMsgType.IDENT_REPLY)
        runtime_id = self._read_chunk(4)
        if runtime_id != b"AROR":
            raise UnsupportedDevice("Unsupported runtime ID: {}"
                                    .format(runtime_id))
        gateware_version = self._read_chunk(self._read_length).decode("utf-8")
        if gateware_version != software_version:
            logger.warning("Mismatch between gateware (%s) "
                           "and software (%s) versions",
                           gateware_version, software_version)

    def switch_clock(self, external):
        self._write_header(_H2DMsgType.SWITCH_CLOCK)
        self._write_int8(external)
        self._write_flush()

        self._read_empty(_D2HMsgType.CLOCK_SWITCH_COMPLETED)

    def get_log(self):
        self._write_empty(_H2DMsgType.LOG_REQUEST)

        self._read_header()
        self._read_expect(_D2HMsgType.LOG_REPLY)
        return self._read_chunk(self._read_length).decode("utf-8")

    def clear_log(self):
        self._write_empty(_H2DMsgType.LOG_CLEAR)

        self._read_empty(_D2HMsgType.LOG_REPLY)

    def flash_storage_read(self, key):
        self._write_header(_H2DMsgType.FLASH_READ_REQUEST)
        self._write_string(key)
        self._write_flush()

        self._read_header()
        self._read_expect(_D2HMsgType.FLASH_READ_REPLY)
        return self._read_chunk(self._read_length)

    def flash_storage_write(self, key, value):
        self._write_header(_H2DMsgType.FLASH_WRITE_REQUEST)
        self._write_string(key)
        self._write_bytes(value)
        self._write_flush()

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
        self._write_flush()

        self._read_empty(_D2HMsgType.FLASH_OK_REPLY)

    def load(self, kernel_library):
        self._write_header(_H2DMsgType.LOAD_LIBRARY)
        self._write_chunk(kernel_library)
        self._write_flush()

        self._read_empty(_D2HMsgType.LOAD_COMPLETED)

    def run(self):
        self._write_empty(_H2DMsgType.RUN_KERNEL)
        logger.debug("running kernel")

    _rpc_sentinel = object()
    _rpc_undefined = object()

    # See session.c:{send,receive}_rpc_value and llvm_ir_generator.py:_rpc_tag.
    def _receive_rpc_value(self, object_map):
        tag = chr(self._read_int8())
        if tag == "\x00":
            return self._rpc_sentinel
        elif tag == "t":
            length = self._read_int8()
            return tuple(self._receive_rpc_value(object_map) for _ in range(length))
        elif tag == "n":
            return None
        elif tag == "b":
            return bool(self._read_int8())
        elif tag == "i":
            return self._read_int32()
        elif tag == "I":
            return self._read_int64()
        elif tag == "f":
            return self._read_float64()
        elif tag == "F":
            numerator   = self._read_int64()
            denominator = self._read_int64()
            return Fraction(numerator, denominator)
        elif tag == "s":
            return self._read_string()
        elif tag == "l":
            length = self._read_int32()
            return [self._receive_rpc_value(object_map) for _ in range(length)]
        elif tag == "r":
            start = self._receive_rpc_value(object_map)
            stop  = self._receive_rpc_value(object_map)
            step  = self._receive_rpc_value(object_map)
            return range(start, stop, step)
        elif tag == "o":
            present = self._read_int8()
            if present:
                return self._receive_rpc_value(object_map)
            else:
                return self._rpc_undefined
        elif tag == "O":
            return object_map.retrieve(self._read_int32())
        else:
            raise IOError("Unknown RPC value tag: {}".format(repr(tag)))

    def _receive_rpc_args(self, object_map, defaults):
        args = []
        default_arg_num = 0
        while True:
            value = self._receive_rpc_value(object_map)
            if value is self._rpc_sentinel:
                return args
            elif value is self._rpc_undefined:
                args.append(defaults[default_arg_num])
                default_arg_num += 1
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
            check(isinstance(value, int) and (-2**31 < value < 2**31-1),
                  lambda: "32-bit int")
            self._write_int32(value)
        elif tag == "I":
            check(isinstance(value, int) and (-2**63 < value < 2**63-1),
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

    def _serve_rpc(self, object_map):
        service_id  = self._read_int32()
        service     = object_map.retrieve(service_id)
        arguments   = self._receive_rpc_args(object_map, service.__defaults__)
        return_tags = self._read_bytes()
        logger.debug("rpc service: [%d]%r %r -> %s", service_id, service, arguments, return_tags)

        try:
            result = service(*arguments)
            logger.debug("rpc service: %d %r == %r", service_id, arguments, result)

            self._write_header(_H2DMsgType.RPC_REPLY)
            self._write_bytes(return_tags)
            self._send_rpc_value(bytearray(return_tags), result, result, service)
            self._write_flush()
        except Exception as exn:
            logger.debug("rpc service: %d %r ! %r", service_id, arguments, exn)

            self._write_header(_H2DMsgType.RPC_EXCEPTION)

            if hasattr(exn, 'artiq_exception'):
                exn = exn.artiq_exception
                self._write_string(exn.name)
                self._write_string(exn.message)
                for index in range(3):
                    self._write_int64(exn.param[index])

                filename, line, column, function = exn.traceback[-1]
                self._write_string(filename)
                self._write_int32(line)
                self._write_int32(column)
                self._write_string(function)
            else:
                exn_type = type(exn)
                if exn_type in (ZeroDivisionError, ValueError, IndexError):
                    self._write_string("0:{}".format(exn_type.__name__))
                else:
                    exn_id = object_map.store(exn_type)
                    self._write_string("{}:{}.{}".format(exn_id,
                                                         exn_type.__module__, exn_type.__qualname__))
                self._write_string(str(exn))
                for index in range(3):
                    self._write_int64(0)

                (_, (filename, line, function, _), ) = traceback.extract_tb(exn.__traceback__, 2)
                self._write_string(filename)
                self._write_int32(line)
                self._write_int32(-1) # column not known
                self._write_string(function)

            self._write_flush()

    def _serve_exception(self, object_map, symbolizer):
        name      = self._read_string()
        message   = self._read_string()
        params    = [self._read_int64() for _ in range(3)]

        filename  = self._read_string()
        line      = self._read_int32()
        column    = self._read_int32()
        function  = self._read_string()

        backtrace = [self._read_int32() for _ in range(self._read_int32())]

        traceback = list(reversed(symbolizer(backtrace))) + \
                    [(filename, line, column, function, None)]
        exception = core_language.ARTIQException(name, message, params, traceback)

        if hasattr(exceptions, exception.name):
            python_exn_type = getattr(exceptions, exception.name)
        else:
            assert exception.id != 0
            python_exn_type = object_map.retrieve(exception.id)

        python_exn = python_exn_type(message)
        python_exn.artiq_exception = exception
        raise python_exn

    def serve(self, object_map, symbolizer):
        while True:
            self._read_header()
            if self._read_type == _D2HMsgType.RPC_REQUEST:
                self._serve_rpc(object_map)
            elif self._read_type == _D2HMsgType.KERNEL_EXCEPTION:
                self._serve_exception(object_map, symbolizer)
            else:
                self._read_expect(_D2HMsgType.KERNEL_FINISHED)
                return
