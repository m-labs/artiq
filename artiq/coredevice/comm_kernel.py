import struct
import logging
import traceback
import numpy
import socket
from enum import Enum
from fractions import Fraction
from collections import namedtuple

from artiq.coredevice import exceptions
from artiq.coredevice.comm import initialize_connection
from artiq import __version__ as software_version


logger = logging.getLogger(__name__)


class Request(Enum):
    SystemInfo = 3

    LoadKernel = 5
    RunKernel = 6

    RPCReply = 7
    RPCException = 8


class Reply(Enum):
    SystemInfo = 2

    LoadCompleted = 5
    LoadFailed = 6

    KernelFinished = 7
    KernelStartupFailed = 8
    KernelException = 9

    RPCRequest = 10

    ClockFailure = 15


class UnsupportedDevice(Exception):
    pass


class LoadError(Exception):
    pass


class RPCReturnValueError(ValueError):
    pass


RPCKeyword = namedtuple('RPCKeyword', ['name', 'value'])


def _receive_fraction(kernel, embedding_map):
    numerator = kernel._read_int64()
    denominator = kernel._read_int64()
    return Fraction(numerator, denominator)


def _receive_list(kernel, embedding_map):
    length = kernel._read_int32()
    tag = chr(kernel._read_int8())
    if tag == "b":
        buffer = kernel._read(length)
        return [bool(a) for a in buffer]
    elif tag == "i":
        buffer = kernel._read(4 * length)
        return list(struct.unpack(kernel.endian + "%sl" % length, buffer))
    elif tag == "I":
        buffer = kernel._read(8 * length)
        return list(struct.unpack(kernel.endian + "%sq" % length, buffer))
    elif tag == "f":
        buffer = kernel._read(8 * length)
        return list(struct.unpack(kernel.endian + "%sd" % length, buffer))
    else:
        fn = receivers[tag]
        elems = []
        for _ in range(length):
            # discard tag, as our device would still send the tag for each
            # non-primitive elements.
            kernel._read_int8()
            item = fn(kernel, embedding_map)
            elems.append(item)
        return elems


def _receive_array(kernel, embedding_map):
    num_dims = kernel._read_int8()
    shape = tuple(kernel._read_int32() for _ in range(num_dims))
    tag = chr(kernel._read_int8())
    fn = receivers[tag]
    length = numpy.prod(shape)
    if tag == "b":
        buffer = kernel._read(length)
        elems = numpy.ndarray((length, ), '?', buffer)
    elif tag == "i":
        buffer = kernel._read(4 * length)
        elems = numpy.ndarray((length, ), kernel.endian + 'i4', buffer)
    elif tag == "I":
        buffer = kernel._read(8 * length)
        elems = numpy.ndarray((length, ), kernel.endian + 'i8', buffer)
    elif tag == "f":
        buffer = kernel._read(8 * length)
        elems = numpy.ndarray((length, ), kernel.endian + 'd', buffer)
    else:
        fn = receivers[tag]
        elems = []
        for _ in range(numpy.prod(shape)):
            # discard the tag
            kernel._read_int8()
            item = fn(kernel, embedding_map)
            elems.append(item)
        elems = numpy.array(elems)
    return elems.reshape(shape)


def _receive_range(kernel, embedding_map):
    start = kernel._receive_rpc_value(embedding_map)
    stop = kernel._receive_rpc_value(embedding_map)
    step = kernel._receive_rpc_value(embedding_map)
    return range(start, stop, step)


def _receive_keyword(kernel, embedding_map):
    name = kernel._read_string()
    value = kernel._receive_rpc_value(embedding_map)
    return RPCKeyword(name, value)


receivers = {
    "\x00": lambda kernel, embedding_map: kernel._rpc_sentinel,
    "t": lambda kernel, embedding_map:
    tuple(kernel._receive_rpc_value(embedding_map)
          for _ in range(kernel._read_int8())),
    "n": lambda kernel, embedding_map: None,
    "b": lambda kernel, embedding_map: bool(kernel._read_int8()),
    "i": lambda kernel, embedding_map: numpy.int32(kernel._read_int32()),
    "I": lambda kernel, embedding_map: numpy.int64(kernel._read_int64()),
    "f": lambda kernel, embedding_map: kernel._read_float64(),
    "s": lambda kernel, embedding_map: kernel._read_string(),
    "B": lambda kernel, embedding_map: kernel._read_bytes(),
    "A": lambda kernel, embedding_map: kernel._read_bytes(),
    "O": lambda kernel, embedding_map:
    embedding_map.retrieve_object(kernel._read_int32()),
    "F": _receive_fraction,
    "l": _receive_list,
    "a": _receive_array,
    "r": _receive_range,
    "k": _receive_keyword
}


class CommKernelDummy:
    def __init__(self):
        pass

    def load(self, kernel_library):
        pass

    def run(self):
        pass

    def serve(self, embedding_map, symbolizer, demangler):
        pass

    def check_system_info(self):
        pass


class CommKernel:
    warned_of_mismatch = False

    def __init__(self, host, port=1381):
        self._read_type = None
        self.host = host
        self.port = port
        self.read_buffer = bytearray()
        self.write_buffer = bytearray()


    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = initialize_connection(self.host, self.port)
        self.socket.sendall(b"ARTIQ coredev\n")
        endian = self._read(1)
        if endian == b"e":
            self.endian = "<"
        elif endian == b"E":
            self.endian = ">"
        else:
            raise IOError("Incorrect reply from device: expected e/E.")
        self.unpack_int32 = struct.Struct(self.endian + "l").unpack
        self.unpack_int64 = struct.Struct(self.endian + "q").unpack
        self.unpack_float64 = struct.Struct(self.endian + "d").unpack

        self.pack_header = struct.Struct(self.endian + "lB").pack
        self.pack_int32 = struct.Struct(self.endian + "l").pack
        self.pack_int64 = struct.Struct(self.endian + "q").pack
        self.pack_float64 = struct.Struct(self.endian + "d").pack

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket
        logger.debug("disconnected")

    #
    # Reader interface
    #

    def _read(self, length):
        # cache the reads to avoid frequent call to recv
        while len(self.read_buffer) < length:
            # the number is just the maximum amount
            # when there is not much data, it would return earlier
            diff = length - len(self.read_buffer)
            flag = 0
            if diff > 8192:
                flag |= socket.MSG_WAITALL
            new_buffer = self.socket.recv(8192, flag)
            if not new_buffer:
                raise ConnectionResetError("Core device connection closed unexpectedly")
            self.read_buffer += new_buffer
        result = self.read_buffer[:length]
        self.read_buffer = self.read_buffer[length:]
        return result

    def _read_header(self):
        self.open()

        # Wait for a synchronization sequence, 5a 5a 5a 5a.
        sync_count = 0
        while sync_count < 4:
            sync_byte = self._read(1)[0]
            if sync_byte == 0x5a:
                sync_count += 1
            else:
                sync_count = 0

        # Read message header.
        raw_type = self._read(1)[0]
        self._read_type = Reply(raw_type)

        logger.debug("receiving message: type=%r",
                     self._read_type)

    def _read_expect(self, ty):
        if self._read_type != ty:
            raise IOError("Incorrect reply from device: {} (expected {})".
                          format(self._read_type, ty))

    def _read_empty(self, ty):
        self._read_header()
        self._read_expect(ty)

    def _read_int8(self):
        return self._read(1)[0]

    def _read_int32(self):
        (value, ) = self.unpack_int32(self._read(4))
        return value

    def _read_int64(self):
        (value, ) = self.unpack_int64(self._read(8))
        return value

    def _read_float64(self):
        (value, ) = self.unpack_float64(self._read(8))
        return value

    def _read_bool(self):
        return True if self._read_int8() else False

    def _read_bytes(self):
        return self._read(self._read_int32())

    def _read_string(self):
        return self._read_bytes().decode("utf-8")

    #
    # Writer interface
    #

    def _write(self, data):
        self.write_buffer += data
        # if the buffer is already pretty large, send it
        # the block size is arbitrary, tuning it may improve performance
        if len(self.write_buffer) > 4096:
            self._flush()

    def _flush(self):
        self.socket.sendall(self.write_buffer)
        self.write_buffer.clear()

    def _write_header(self, ty):
        self.open()

        logger.debug("sending message: type=%r", ty)

        # Write synchronization sequence and header.
        self._write(self.pack_header(0x5a5a5a5a, ty.value))

    def _write_empty(self, ty):
        self._write_header(ty)

    def _write_chunk(self, chunk):
        self._write(chunk)

    def _write_int8(self, value):
        self._write(value)

    def _write_int32(self, value):
        self._write(self.pack_int32(value))

    def _write_int64(self, value):
        self._write(self.pack_int64(value))

    def _write_float64(self, value):
        self._write(self.pack_float64(value))

    def _write_bool(self, value):
        self._write(b'\x01' if value else b'\x00')

    def _write_bytes(self, value):
        self._write_int32(len(value))
        self._write(value)

    def _write_string(self, value):
        self._write_bytes(value.encode("utf-8"))

    #
    # Exported APIs
    #

    def check_system_info(self):
        self._write_empty(Request.SystemInfo)
        self._flush()

        self._read_header()
        self._read_expect(Reply.SystemInfo)
        runtime_id = self._read(4)
        if runtime_id == b"AROR":
            gateware_version = self._read_string().split(";")[0]
            if gateware_version != software_version and not self.warned_of_mismatch:
                logger.warning("Mismatch between gateware (%s) "
                               "and software (%s) versions",
                               gateware_version, software_version)
                CommKernel.warned_of_mismatch = True

            finished_cleanly = self._read_bool()
            if not finished_cleanly:
                logger.warning("Previous kernel did not cleanly finish")
        elif runtime_id == b"ARZQ":
            pass
        else:
            raise UnsupportedDevice("Unsupported runtime ID: {}"
                                    .format(runtime_id))

    def load(self, kernel_library):
        self._write_header(Request.LoadKernel)
        self._write_bytes(kernel_library)
        self._flush()

        self._read_header()
        if self._read_type == Reply.LoadFailed:
            raise LoadError(self._read_string())
        else:
            self._read_expect(Reply.LoadCompleted)

    def run(self):
        self._write_empty(Request.RunKernel)
        self._flush()
        logger.debug("running kernel")

    _rpc_sentinel = object()

    # See rpc_proto.rs and compiler/ir.py:rpc_tag.
    def _receive_rpc_value(self, embedding_map):
        tag = chr(self._read_int8())
        if tag in receivers:
            return receivers.get(tag)(self, embedding_map)
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
        tag = chr(tags.pop(0))
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
            self._write_bool(value)
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
            tag_element = chr(tags[0])
            if tag_element == "b":
                self._write(bytes(value))
            elif tag_element == "i":
                self._write(struct.pack(self.endian + "%sl" %
                                        len(value), *value))
            elif tag_element == "I":
                self._write(struct.pack(self.endian + "%sq" %
                                        len(value), *value))
            elif tag_element == "f":
                self._write(struct.pack(self.endian + "%sd" %
                                        len(value), *value))
            else:
                for elt in value:
                    tags_copy = bytearray(tags)
                    self._send_rpc_value(tags_copy, elt, root, function)
            self._skip_rpc_value(tags)
        elif tag == "a":
            check(isinstance(value, numpy.ndarray),
                  lambda: "numpy.ndarray")
            num_dims = tags.pop(0)
            check(num_dims == len(value.shape),
                  lambda: "{}-dimensional numpy.ndarray".format(num_dims))
            for s in value.shape:
                self._write_int32(s)
            tag_element = chr(tags[0])
            if tag_element == "b":
                self._write(value.reshape((-1,), order="C").tobytes())
            elif tag_element == "i":
                array = value.reshape(
                    (-1,), order="C").astype(self.endian + 'i4')
                self._write(array.tobytes())
            elif tag_element == "I":
                array = value.reshape(
                    (-1,), order="C").astype(self.endian + 'i8')
                self._write(array.tobytes())
            elif tag_element == "f":
                array = value.reshape(
                    (-1,), order="C").astype(self.endian + 'd')
                self._write(array.tobytes())
            else:
                for elt in value.reshape((-1,), order="C"):
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
        is_async = self._read_bool()
        service_id = self._read_int32()
        args, kwargs = self._receive_rpc_args(embedding_map)
        return_tags = self._read_bytes()

        if service_id == 0:
            def service(obj, attr, value): return setattr(obj, attr, value)
        else:
            service = embedding_map.retrieve_object(service_id)
        logger.debug("rpc service: [%d]%r%s %r %r -> %s", service_id, service,
                     (" (async)" if is_async else ""), args, kwargs, return_tags)

        if is_async:
            service(*args, **kwargs)
            return

        try:
            result = service(*args, **kwargs)
            logger.debug("rpc service: %d %r %r = %r",
                         service_id, args, kwargs, result)

            self._write_header(Request.RPCReply)
            self._write_bytes(return_tags)
            self._send_rpc_value(bytearray(return_tags),
                                 result, result, service)
            self._flush()
        except RPCReturnValueError as exn:
            raise
        except Exception as exn:
            logger.debug("rpc service: %d %r %r ! %r",
                         service_id, args, kwargs, exn)

            self._write_header(Request.RPCException)

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
                if exn_type in (ZeroDivisionError, ValueError, IndexError, RuntimeError) or \
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
                self._write_int32(-1)  # column not known
                self._write_string(function)
            self._flush()

    def _serve_exception(self, embedding_map, symbolizer, demangler):
        name = self._read_string()
        message = self._read_string()
        params = [self._read_int64() for _ in range(3)]

        filename = self._read_string()
        line = self._read_int32()
        column = self._read_int32()
        function = self._read_string()

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
            if self._read_type == Reply.RPCRequest:
                self._serve_rpc(embedding_map)
            elif self._read_type == Reply.KernelException:
                self._serve_exception(embedding_map, symbolizer, demangler)
            elif self._read_type == Reply.ClockFailure:
                raise exceptions.ClockFailure
            else:
                self._read_expect(Reply.KernelFinished)
                return
