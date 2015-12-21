from operator import itemgetter
from collections import namedtuple
from itertools import count
from enum import Enum
import struct
import logging


logger = logging.getLogger(__name__)


class MessageType(Enum):
    output = 0b00
    input = 0b01
    exception = 0b10


class ExceptionType(Enum):
    reset_rising = 0b000000
    reset_falling = 0b000001
    reset_phy_rising = 0b000010
    reset_phy_falling = 0b000011

    o_underflow_reset = 0b010000
    o_sequence_error_reset = 0b010001
    o_collision_error_reset = 0b010010

    i_overflow_reset = 0b100000


OutputMessage = namedtuple(
    "OutputMessage", "channel timestamp rtio_counter address data")

InputMessage = namedtuple(
    "InputMessage", "channel timestamp rtio_counter data")

ExceptionMessage = namedtuple(
    "ExceptionMessage", "channel rtio_counter exception_type")


def decode_message(data):
    message_type_channel = struct.unpack(">I", data[28:32])[0]
    message_type = MessageType(message_type_channel & 0b11)
    channel = message_type_channel >> 2

    if message_type == MessageType.output:
        parts = struct.unpack(">QIQQ", data[:28])
        data, address, rtio_counter, timestamp = parts
        return OutputMessage(channel, timestamp, rtio_counter, address, data)
    elif message_type == MessageType.input:
        parts = struct.unpack(">QIQQ", data[:28])
        data, _, rtio_counter, timestamp = parts
        return InputMessage(channel, timestamp, rtio_counter, data)
    elif message_type == MessageType.exception:
        exception_type, rtio_counter = struct.unpack(">BQ", data[11:20])
        return ExceptionMessage(channel, rtio_counter,
                                ExceptionType(exception_type))


def decode_dump(data):
    parts = struct.unpack(">IQbbbb", data[:16])
    (sent_bytes, total_byte_count,
     overflow_occured, log_channel, dds_channel, _) = parts

    if sent_bytes + 16 != len(data):
        raise ValueError("analyzer dump has incorrect length")
    if overflow_occured:
        logger.warning("analyzer FIFO overflow occured, "
                       "some messages have been lost")
    if total_byte_count > sent_bytes:
        logger.info("analyzer ring buffer has wrapped %d times",
                    total_byte_count//sent_bytes)

    position = 16
    messages = []
    for _ in range(sent_bytes//32):
        messages.append(decode_message(data[position:position+32]))
        position += 32
    return messages


def vcd_codes():
    codechars = [chr(i) for i in range(33, 127)]
    for n in count():
        q, r = divmod(n, len(codechars))
        code = codechars[r]
        while q > 0:
            q, r = divmod(q, len(codechars))
            code = codechars[r] + code
        yield code


class VCDChannel:
    def __init__(self, out, code):
        self.out = out
        self.code = code

    def set_value(self, value):
        if len(value) > 1:
            self.out.write("b" + value + " " + self.code + "\n")
        else:
            self.out.write(value + self.code + "\n")


class VCDManager:
    def __init__(self, filename):
        self.out = open(filename, "w")
        self.codes = vcd_codes()
        self.current_time = None

    def set_timescale_ns(self, timescale):
        self.out.write("$timescale {}ns $end\n".format(timescale))

    def get_channel(self, name, width):
        code = next(self.codes)
        self.out.write("$var wire {width} {code} {name} $end\n"
                       .format(name=name, code=code, width=width))
        return VCDChannel(self.out, code)

    def set_time(self, time):
        if time != self.current_time:
            self.out.write("#{}\n".format(time))
            self.current_time = time

    def close(self):
        self.out.close()


class TTLHandler:
    def __init__(self, vcd_manager, name):
        self.channel_value = vcd_manager.get_channel(name, 1)
        self.last_value = "X"
        self.oe = True

    def process_message(self, message):
        if isinstance(message, OutputMessage):
            if message.address == 0:
                self.last_value = str(message.data)
                if self.oe:
                    self.channel_value.set_value(self.last_value)
            elif messages.address == 1:
                self.oe = bool(message.data)
                if self.oe:
                    self.channel_value.set_value(self.last_value)
                else:
                    self.channel_value.set_value("X")


def get_timescale(devices):
    timescale = None
    for desc in devices.values():
        if isinstance(desc, dict) and desc["type"] == "local":
            if (desc["module"] == "artiq.coredevice.core"
                    and desc["class"] == "Core"):
                if timescale is None:
                    timescale = desc["arguments"]["ref_period"]*1e9
                else:
                    return None  # more than one core device found
    return timescale


def create_channel_handlers(vcd_manager, devices):
    channel_handlers = dict()
    for name, desc in sorted(devices.items(), key=itemgetter(0)):
        if isinstance(desc, dict) and desc["type"] == "local":
            if (desc["module"] == "artiq.coredevice.ttl"
                    and desc["class"] in {"TTLOut", "TTLInOut"}):
                channel = desc["arguments"]["channel"]
                channel_handlers[channel] = TTLHandler(vcd_manager, name)
    return channel_handlers


def get_message_time(message):
    return getattr(message, "timestamp", message.rtio_counter)


def messages_to_vcd(filename, devices, messages):
    vcd_manager = VCDManager(filename)
    try:
        timescale = get_timescale(devices)
        if timescale is not None:
            vcd_manager.set_timescale_ns(timescale)
        else:
            logger.warning("unable to determine VCD timescale")

        channel_handlers = create_channel_handlers(vcd_manager, devices)

        vcd_manager.set_time(0)
        messages = sorted(messages, key=get_message_time)
        if messages:
            start_time = get_message_time(messages[0])
            for message in messages:
                if message.channel in channel_handlers:
                    vcd_manager.set_time(
                        get_message_time(message) - start_time)
                    channel_handlers[message.channel].process_message(message)
    finally:
        vcd_manager.close()
