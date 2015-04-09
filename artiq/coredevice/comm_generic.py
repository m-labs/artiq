import struct
import zlib
import logging
from enum import Enum
from fractions import Fraction

from artiq.language import units
from artiq.coredevice.runtime import Environment
from artiq.coredevice import runtime_exceptions
from artiq.language import core as core_language
from artiq.coredevice.rpc_wrapper import RPCWrapper


logger = logging.getLogger(__name__)


class _H2DMsgType(Enum):
    LINK_MESSAGE = 1

    REQUEST_IDENT = 2
    SWITCH_CLOCK = 3

    LOAD_OBJECT = 4
    RUN_KERNEL = 5
    

class _D2HMsgType(Enum):
    MESSAGE_UNRECOGNIZED = 1
    LOG = 2

    IDENT = 3
    CLOCK_SWITCH_COMPLETED = 4
    CLOCK_SWITCH_FAILED = 5

    OBJECT_LOADED = 6
    OBJECT_INCORRECT_LENGTH = 7
    OBJECT_CRC_FAILED = 8
    OBJECT_UNRECOGNIZED = 9

    KERNEL_FINISHED = 10
    KERNEL_STARTUP_FAILED = 11
    KERNEL_EXCEPTION = 12

    RPC_REQUEST = 13


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

    def _read(self, length):
        self.open()
        return self.read(length)

    def _write(self, data):
        self.open()
        self.write(data)

    def _get_device_msg(self):
        while True:
            (reply, ) = struct.unpack("B", self._read(1))
            msg = _D2HMsgType(reply)
            if msg == _D2HMsgType.LOG:
                (length, ) = struct.unpack(">h", self._read(2))
                log_message = ""
                for i in range(length):
                    (c, ) = struct.unpack("B", self._read(1))
                    log_message += chr(c)
                logger.info("DEVICE LOG: %s", log_message)
            else:
                logger.debug("message received: %r", msg)
                return msg

    def get_runtime_env(self):
        self._write(struct.pack(">lb", 0x5a5a5a5a,
                                _H2DMsgType.REQUEST_IDENT.value))
        msg = self._get_device_msg()
        if msg != _D2HMsgType.IDENT:
            raise IOError("Incorrect reply from device: {}".format(msg))
        (reply, ) = struct.unpack("B", self._read(1))
        runtime_id = chr(reply)
        for i in range(3):
            (reply, ) = struct.unpack("B", self._read(1))
            runtime_id += chr(reply)
        if runtime_id != "AROR":
            raise UnsupportedDevice("Unsupported runtime ID: {}"
                                    .format(runtime_id))
        ref_freq_i, ref_freq_fn, ref_freq_fd = struct.unpack(
            ">lBB", self._read(6))
        ref_freq = (ref_freq_i + Fraction(ref_freq_fn, ref_freq_fd))*units.Hz
        ref_period = 1/ref_freq
        logger.debug("environment ref_period: %s", ref_period)
        return Environment(ref_period)

    def switch_clock(self, external):
        self._write(struct.pack(
            ">lbb", 0x5a5a5a5a, _H2DMsgType.SWITCH_CLOCK.value,
            int(external)))
        msg = self._get_device_msg()
        if msg != _D2HMsgType.CLOCK_SWITCH_COMPLETED:
            raise IOError("Incorrect reply from device: {}".format(msg))

    def load(self, kcode):
        self._write(struct.pack(
            ">lblL",
            0x5a5a5a5a, _H2DMsgType.LOAD_OBJECT.value,
            len(kcode), zlib.crc32(kcode)))
        self._write(kcode)
        msg = self._get_device_msg()
        if msg != _D2HMsgType.OBJECT_LOADED:
            raise IOError("Incorrect reply from device: "+str(msg))

    def run(self, kname):
        self._write(struct.pack(
            ">lbl", 0x5a5a5a5a, _H2DMsgType.RUN_KERNEL.value, len(kname)))
        for c in kname:
            self._write(struct.pack(">B", ord(c)))
        logger.debug("running kernel: %s", kname)



    def _receive_rpc_values(self):
        r = []
        while True:
            type_tag = chr(struct.unpack(">B", self._read(1))[0])
            if type_tag == "\x00":
                return r
            if type_tag == "n":
                r.append(None)
            if type_tag == "b":
                r.append(bool(struct.unpack(">B", self._read(1))[0]))
            if type_tag == "i":
                r.append(struct.unpack(">l", self._read(4))[0])
            if type_tag == "I":
                r.append(struct.unpack(">q", self._read(8))[0])
            if type_tag == "f":
                r.append(struct.unpack(">d", self._read(8))[0])
            if type_tag == "F":
                n, d = struct.unpack(">qq", self._read(16))
                r.append(Fraction(n, d))
            if type_tag == "l":
                r.append(self._receive_rpc_values())

    def _serve_rpc(self, rpc_wrapper, rpc_map, user_exception_map):
        rpc_num = struct.unpack(">h", self._read(2))[0]
        args = self._receive_rpc_values()
        logger.debug("rpc service: %d %r", rpc_num, args)
        eid, r = rpc_wrapper.run_rpc(
            user_exception_map, rpc_map[rpc_num], args)
        self._write(struct.pack(">ll", eid, r))
        logger.debug("rpc service: %d %r == %r", rpc_num, args, r)

    def _serve_exception(self, rpc_wrapper, user_exception_map):
        eid, p0, p1, p2 = struct.unpack(">lqqq", self._read(4+3*8))
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
            msg = self._get_device_msg()
            if msg == _D2HMsgType.RPC_REQUEST:
                self._serve_rpc(rpc_wrapper, rpc_map, user_exception_map)
            elif msg == _D2HMsgType.KERNEL_EXCEPTION:
                self._serve_exception(rpc_wrapper, user_exception_map)
            elif msg == _D2HMsgType.KERNEL_FINISHED:
                return
            else:
                raise IOError("Incorrect request from device: "+str(msg))

    def send_link_message(self, data):
        self._write(struct.pack(
            ">lb", 0x5a5a5a5a, _H2DMsgType.LINK_MESSAGE.value))
        self._write(data)
