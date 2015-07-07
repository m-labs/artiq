import struct
import logging
from enum import Enum
from fractions import Fraction

from artiq.coredevice import runtime_exceptions
from artiq.language import core as core_language
from artiq.coredevice.rpc_wrapper import RPCWrapper


logger = logging.getLogger(__name__)


class _H2DMsgType(Enum):
    LOG_REQUEST = 1
    IDENT_REQUEST = 2
    SWITCH_CLOCK = 3

    LOAD_OBJECT = 4
    RUN_KERNEL = 5

    RPC_REPLY = 6

    FLASH_READ_REQUEST = 7
    FLASH_WRITE_REQUEST = 8
    FLASH_ERASE_REQUEST = 9
    FLASH_REMOVE_REQUEST = 10


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


class CommGeneric:
    # methods for derived classes to implement
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

    def _read_header(self):
        self.open()

        sync_count = 0
        while sync_count < 4:
            (c, ) = struct.unpack("B", self.read(1))
            if c == 0x5a:
                sync_count += 1
            else:
                sync_count = 0
        length = struct.unpack(">l", self.read(4))[0]
        if not length:  # inband connection close
            raise OSError("Connection closed")
        tyv = struct.unpack("B", self.read(1))[0]
        ty = _D2HMsgType(tyv)
        logger.debug("receiving message: type=%r length=%d", ty, length)
        return length, ty

    def _write_header(self, length, ty):
        self.open()
        logger.debug("sending message: type=%r length=%d", ty, length)
        self.write(struct.pack(">ll", 0x5a5a5a5a, length))
        if ty is not None:
            self.write(struct.pack("B", ty.value))

    def reset_session(self):
        self._write_header(0, None)

    def check_ident(self):
        self._write_header(9, _H2DMsgType.IDENT_REQUEST)
        _, ty = self._read_header()
        if ty != _D2HMsgType.IDENT_REPLY:
            raise IOError("Incorrect reply from device: {}".format(ty))
        (reply, ) = struct.unpack("B", self.read(1))
        runtime_id = chr(reply)
        for i in range(3):
            (reply, ) = struct.unpack("B", self.read(1))
            runtime_id += chr(reply)
        if runtime_id != "AROR":
            raise UnsupportedDevice("Unsupported runtime ID: {}"
                                    .format(runtime_id))

    def switch_clock(self, external):
        self._write_header(10, _H2DMsgType.SWITCH_CLOCK)
        self.write(struct.pack("B", int(external)))
        _, ty = self._read_header()
        if ty != _D2HMsgType.CLOCK_SWITCH_COMPLETED:
            raise IOError("Incorrect reply from device: {}".format(ty))

    def load(self, kcode):
        self._write_header(len(kcode) + 9, _H2DMsgType.LOAD_OBJECT)
        self.write(kcode)
        _, ty = self._read_header()
        if ty != _D2HMsgType.LOAD_COMPLETED:
            raise IOError("Incorrect reply from device: "+str(ty))

    def run(self, kname):
        self._write_header(len(kname) + 9, _H2DMsgType.RUN_KERNEL)
        self.write(bytes(kname, "ascii"))
        logger.debug("running kernel: %s", kname)

    def flash_storage_read(self, key):
        self._write_header(9+len(key), _H2DMsgType.FLASH_READ_REQUEST)
        self.write(key)
        length, ty = self._read_header()
        if ty != _D2HMsgType.FLASH_READ_REPLY:
            raise IOError("Incorrect reply from device: {}".format(ty))
        value = self.read(length - 9)
        return value

    def flash_storage_write(self, key, value):
        self._write_header(9+len(key)+1+len(value),
                           _H2DMsgType.FLASH_WRITE_REQUEST)
        self.write(key)
        self.write(b"\x00")
        self.write(value)
        _, ty = self._read_header()
        if ty != _D2HMsgType.FLASH_OK_REPLY:
            if ty == _D2HMsgType.FLASH_ERROR_REPLY:
                raise IOError("Flash storage is full")
            else:
                raise IOError("Incorrect reply from device: {}".format(ty))

    def flash_storage_erase(self):
        self._write_header(9, _H2DMsgType.FLASH_ERASE_REQUEST)
        _, ty = self._read_header()
        if ty != _D2HMsgType.FLASH_OK_REPLY:
            raise IOError("Incorrect reply from device: {}".format(ty))

    def flash_storage_remove(self, key):
        self._write_header(9+len(key), _H2DMsgType.FLASH_REMOVE_REQUEST)
        self.write(key)
        _, ty = self._read_header()
        if ty != _D2HMsgType.FLASH_OK_REPLY:
            raise IOError("Incorrect reply from device: {}".format(ty))

    def _receive_rpc_value(self, type_tag):
        if type_tag == "n":
            return None
        if type_tag == "b":
            return bool(struct.unpack("B", self.read(1))[0])
        if type_tag == "i":
            return struct.unpack(">l", self.read(4))[0]
        if type_tag == "I":
            return struct.unpack(">q", self.read(8))[0]
        if type_tag == "f":
            return struct.unpack(">d", self.read(8))[0]
        if type_tag == "F":
            n, d = struct.unpack(">qq", self.read(16))
            return Fraction(n, d)

    def _receive_rpc_values(self):
        r = []
        while True:
            type_tag = chr(struct.unpack("B", self.read(1))[0])
            if type_tag == "\x00":
                return r
            elif type_tag == "l":
                elt_type_tag = chr(struct.unpack("B", self.read(1))[0])
                length = struct.unpack(">l", self.read(4))[0]
                r.append([self._receive_rpc_value(elt_type_tag)
                          for i in range(length)])
            else:
                r.append(self._receive_rpc_value(type_tag))

    def _serve_rpc(self, rpc_wrapper, rpc_map, user_exception_map):
        rpc_num = struct.unpack(">l", self.read(4))[0]
        args = self._receive_rpc_values()
        logger.debug("rpc service: %d %r", rpc_num, args)
        eid, r = rpc_wrapper.run_rpc(
            user_exception_map, rpc_map[rpc_num], args)
        self._write_header(9+2*4, _H2DMsgType.RPC_REPLY)
        self.write(struct.pack(">ll", eid, r))
        logger.debug("rpc service: %d %r == %r (eid %d)", rpc_num, args,
                     r, eid)

    def _serve_exception(self, rpc_wrapper, user_exception_map):
        eid, p0, p1, p2 = struct.unpack(">lqqq", self.read(4+3*8))
        rpc_wrapper.filter_rpc_exception(eid)
        if eid < core_language.first_user_eid:
            exception = runtime_exceptions.exception_map[eid]
            raise exception(self.core, p0, p1, p2)
        else:
            exception = user_exception_map[eid]
            raise exception

    def serve(self, rpc_map, user_exception_map):
        rpc_wrapper = RPCWrapper()
        while True:
            _, ty = self._read_header()
            if ty == _D2HMsgType.RPC_REQUEST:
                self._serve_rpc(rpc_wrapper, rpc_map, user_exception_map)
            elif ty == _D2HMsgType.KERNEL_EXCEPTION:
                self._serve_exception(rpc_wrapper, user_exception_map)
            elif ty == _D2HMsgType.KERNEL_FINISHED:
                return
            else:
                raise IOError("Incorrect request from device: "+str(ty))

    def get_log(self):
        self._write_header(9, _H2DMsgType.LOG_REQUEST)
        length, ty = self._read_header()
        if ty != _D2HMsgType.LOG_REPLY:
            raise IOError("Incorrect request from device: "+str(ty))
        r = ""
        for i in range(length - 9):
            c = struct.unpack("B", self.read(1))[0]
            if c:
                r += chr(c)
        return r
