import serial
import struct
import zlib
from enum import Enum
from fractions import Fraction
import logging

from artiq.language import core as core_language
from artiq.language import units
from artiq.language.db import *
from artiq.coredevice.runtime import Environment
from artiq.coredevice import runtime_exceptions
from artiq.coredevice.rpc_wrapper import RPCWrapper


logger = logging.getLogger(__name__)


class UnsupportedDevice(Exception):
    pass


class _H2DMsgType(Enum):
    REQUEST_IDENT = 1
    LOAD_OBJECT = 2
    RUN_KERNEL = 3
    SET_BAUD_RATE = 4
    SWITCH_CLOCK = 5


class _D2HMsgType(Enum):
    LOG = 1
    MESSAGE_UNRECOGNIZED = 2
    IDENT = 3
    OBJECT_LOADED = 4
    INCORRECT_LENGTH = 5
    CRC_FAILED = 6
    OBJECT_UNRECOGNIZED = 7
    KERNEL_FINISHED = 8
    KERNEL_EXCEPTION = 9
    KERNEL_STARTUP_FAILED = 10
    RPC_REQUEST = 11
    CLOCK_SWITCH_COMPLETED = 12
    CLOCK_SWITCH_FAILED = 13


def _write_exactly(f, data):
    remaining = len(data)
    pos = 0
    while remaining:
        written = f.write(data[pos:])
        remaining -= written
        pos += written


def _read_exactly(f, n):
    r = bytes()
    while(len(r) < n):
        r += f.read(n - len(r))
    return r


class Comm(AutoDB):
    class DBKeys:
        serial_dev = Parameter("/dev/ttyUSB1")
        baud_rate = Parameter(115200)
        implicit_core = False

    def build(self):
        self.port = serial.serial_for_url(self.serial_dev, baudrate=115200)
        self.port.flush()
        self.set_remote_baud(self.baud_rate)
        self.set_baud(self.baud_rate)
        self.rpc_wrapper = RPCWrapper()

    def set_baud(self, baud):
        self.port.baudrate = baud
        self.port.flush()
        logger.debug("baud rate set to".format(baud))

    def set_remote_baud(self, baud):
        _write_exactly(self.port, struct.pack(
            ">lbl", 0x5a5a5a5a, _H2DMsgType.SET_BAUD_RATE.value, baud))
        handshake = 0
        fails = 0
        while handshake < 4:
            (recv, ) = struct.unpack("B", _read_exactly(self.port, 1))
            if recv == 0x5a:
                handshake += 1
            else:
                # FIXME: when loading immediately after a board reset,
                # we erroneously get some zeros back.
                logger.warning("unexpected sync character: {:02x}".format(int(recv)))
                handshake = 0
                if recv != 0:
                    fails += 1
                    if fails > 3:
                        raise IOError("Baudrate ack failed")
        self.set_baud(baud)
        logger.debug("synchronized")

    def close(self):
        self.set_remote_baud(115200)
        self.port.close()

    def _get_device_msg(self):
        while True:
            (reply, ) = struct.unpack("B", _read_exactly(self.port, 1))
            msg = _D2HMsgType(reply)
            if msg == _D2HMsgType.LOG:
                (length, ) = struct.unpack(">h", _read_exactly(self.port, 2))
                log_message = ""
                for i in range(length):
                    (c, ) = struct.unpack("B", _read_exactly(self.port, 1))
                    log_message += chr(c)
                logger.info("DEVICE LOG: " + log_message)
            else:
                logger.debug("message received: {!r}".format(msg))
                return msg

    def get_runtime_env(self):
        _write_exactly(self.port, struct.pack(
            ">lb", 0x5a5a5a5a, _H2DMsgType.REQUEST_IDENT.value))
        msg = self._get_device_msg()
        if msg != _D2HMsgType.IDENT:
            raise IOError("Incorrect reply from device: "+str(msg))
        (reply, ) = struct.unpack("B", _read_exactly(self.port, 1))
        runtime_id = chr(reply)
        for i in range(3):
            (reply, ) = struct.unpack("B", _read_exactly(self.port, 1))
            runtime_id += chr(reply)
        if runtime_id != "AROR":
            raise UnsupportedDevice("Unsupported runtime ID: "+runtime_id)
        ref_freq_i, ref_freq_fn, ref_freq_fd = struct.unpack(
            ">lBB", _read_exactly(self.port, 6))
        ref_freq = (ref_freq_i + Fraction(ref_freq_fn, ref_freq_fd))*units.Hz
        ref_period = 1/ref_freq
        logger.debug("environment ref_period: {}".format(ref_period))
        return Environment(ref_period)

    def switch_clock(self, external):
        _write_exactly(self.port, struct.pack(
            ">lbb", 0x5a5a5a5a, _H2DMsgType.SWITCH_CLOCK.value,
            int(external)))
        msg = self._get_device_msg()
        if msg != _D2HMsgType.CLOCK_SWITCH_COMPLETED:
            raise IOError("Incorrect reply from device: "+str(msg))

    def load(self, kcode):
        _write_exactly(self.port, struct.pack(
            ">lblL",
            0x5a5a5a5a, _H2DMsgType.LOAD_OBJECT.value,
            len(kcode), zlib.crc32(kcode)))
        _write_exactly(self.port, kcode)
        msg = self._get_device_msg()
        if msg != _D2HMsgType.OBJECT_LOADED:
            raise IOError("Incorrect reply from device: "+str(msg))

    def run(self, kname):
        _write_exactly(self.port, struct.pack(
            ">lbl", 0x5a5a5a5a, _H2DMsgType.RUN_KERNEL.value, len(kname)))
        for c in kname:
            _write_exactly(self.port, struct.pack(">B", ord(c)))
        logger.debug("running kernel: {}".format(kname))

    def _receive_rpc_values(self):
        r = []
        while True:
            type_tag = chr(struct.unpack(">B", _read_exactly(self.port, 1))[0])
            if type_tag == "\x00":
                return r
            if type_tag == "n":
                r.append(None)
            if type_tag == "b":
                r.append(bool(struct.unpack(">B",
                                            _read_exactly(self.port, 1))[0]))
            if type_tag == "i":
                r.append(struct.unpack(">l", _read_exactly(self.port, 4))[0])
            if type_tag == "I":
                r.append(struct.unpack(">q", _read_exactly(self.port, 8))[0])
            if type_tag == "f":
                r.append(struct.unpack(">d", _read_exactly(self.port, 8))[0])
            if type_tag == "F":
                n, d = struct.unpack(">qq", _read_exactly(self.port, 16))
                r.append(Fraction(n, d))
            if type_tag == "l":
                r.append(self._receive_rpc_values())

    def _serve_rpc(self, rpc_map, user_exception_map):
        rpc_num = struct.unpack(">h", _read_exactly(self.port, 2))[0]
        args = self._receive_rpc_values()
        logger.debug("rpc service: {} ({})".format(rpc_num, args))
        eid, r = self.rpc_wrapper.run_rpc(user_exception_map, rpc_map[rpc_num], args)
        _write_exactly(self.port, struct.pack(">ll", eid, r))
        logger.debug("rpc service: {} ({}) == {}".format(
            rpc_num, args, r))

    def _serve_exception(self, user_exception_map):
        eid = struct.unpack(">l", _read_exactly(self.port, 4))[0]
        self.rpc_wrapper.filter_rpc_exception(eid)
        if eid < core_language.first_user_eid:
            exception = runtime_exceptions.exception_map[eid]
        else:
            exception = user_exception_map[eid]
        raise exception

    def serve(self, rpc_map, user_exception_map):
        while True:
            msg = self._get_device_msg()
            if msg == _D2HMsgType.RPC_REQUEST:
                self._serve_rpc(rpc_map, user_exception_map)
            elif msg == _D2HMsgType.KERNEL_EXCEPTION:
                self._serve_exception(user_exception_map)
            elif msg == _D2HMsgType.KERNEL_FINISHED:
                return
            else:
                raise IOError("Incorrect request from device: "+str(msg))
