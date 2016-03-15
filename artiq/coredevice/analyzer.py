from operator import itemgetter
from collections import namedtuple
from itertools import count
import struct
import logging

from artiq.protocols.analyzer import MessageType, ExceptionType


logger = logging.getLogger(__name__)


OutputMessage = namedtuple(
    "OutputMessage", "channel timestamp rtio_counter address data")

InputMessage = namedtuple(
    "InputMessage", "channel timestamp rtio_counter data")

ExceptionMessage = namedtuple(
    "ExceptionMessage", "channel rtio_counter exception_type")

StoppedMessage = namedtuple(
    "StoppedMessage", "rtio_counter")


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
    elif message_type == MessageType.stopped:
        rtio_counter = struct.unpack(">Q", data[12:20])[0]
        return StoppedMessage(rtio_counter)
    else:
        raise ValueError


DecodedDump = namedtuple(
    "DecodedDump", "log_channel dds_onehot_sel messages")


def decode_dump(data):
    parts = struct.unpack(">IQbbb", data[:15])
    (sent_bytes, total_byte_count,
     overflow_occured, log_channel, dds_onehot_sel) = parts

    expected_len = sent_bytes + 15
    if expected_len != len(data):
        raise ValueError("analyzer dump has incorrect length "
                         "(got {}, expected {})".format(
                            len(data), expected_len))
    if overflow_occured:
        logger.warning("analyzer FIFO overflow occured, "
                       "some messages have been lost")
    if total_byte_count > sent_bytes:
        logger.info("analyzer ring buffer has wrapped %d times",
                    total_byte_count//sent_bytes)

    position = 15
    messages = []
    for _ in range(sent_bytes//32):
        messages.append(decode_message(data[position:position+32]))
        position += 32
    return DecodedDump(log_channel, bool(dds_onehot_sel), messages)


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

    def set_value_double(self, x):
        integer_cast = struct.unpack(">Q", struct.pack(">d", x))[0]
        self.set_value("{:064b}".format(integer_cast))


class VCDManager:
    def __init__(self, fileobj):
        self.out = fileobj
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


class TTLHandler:
    def __init__(self, vcd_manager, name):
        self.name = name
        self.channel_value = vcd_manager.get_channel("ttl/" + name, 1)
        self.last_value = "X"
        self.oe = True

    def process_message(self, message):
        if isinstance(message, OutputMessage):
            logger.debug("TTL write @%d %d to %d, name: %s",
                message.timestamp, message.data, message.address, self.name)
            if message.address == 0:
                self.last_value = str(message.data)
                if self.oe:
                    self.channel_value.set_value(self.last_value)
            elif message.address == 1:
                self.oe = bool(message.data)
                if self.oe:
                    self.channel_value.set_value(self.last_value)
                else:
                    self.channel_value.set_value("X")
        elif isinstance(message, InputMessage):
            logger.debug("TTL read  @%d %d, name: %s",
                message.timestamp, message.data, self.name)
            self.channel_value.set_value(str(message.data))


class TTLClockGenHandler:
    def __init__(self, vcd_manager, name, ref_period):
        self.name = name
        self.ref_period = ref_period
        self.channel_frequency = vcd_manager.get_channel(
            "ttl_clkgen/" + name, 64)

    def process_message(self, message):
        if isinstance(message, OutputMessage):
            logger.debug("TTL_CLKGEN write @%d %d to %d, name: %s",
                message.timestamp, message.data, message.address, self.name)
            frequency = message.data/self.ref_period/2**24
            self.channel_frequency.set_value_double(frequency)


class DDSHandler:
    def __init__(self, vcd_manager, dds_type, onehot_sel, sysclk):
        self.vcd_manager = vcd_manager
        self.dds_type = dds_type
        self.onehot_sel = onehot_sel
        self.sysclk = sysclk

        self.selected_dds_channels = set()
        self.dds_channels = dict()

    def add_dds_channel(self, name, dds_channel_nr):
        dds_channel = dict()
        dds_channel["vcd_frequency"] = \
            self.vcd_manager.get_channel("dds/" + name + "/frequency", 64)
        dds_channel["vcd_phase"] = \
            self.vcd_manager.get_channel("dds/" + name + "/phase", 64)
        if self.dds_type == "AD9858":
            dds_channel["ftw"] = [None, None, None, None]
            dds_channel["pow"] = [None, None]
        elif self.dds_type == "AD9914":
            dds_channel["ftw"] = [None, None]
            dds_channel["pow"] = None
        self.dds_channels[dds_channel_nr] = dds_channel

    def _gpio_to_channels(self, gpio):
        gpio >>= 1  # strip reset
        if self.onehot_sel:
            r = set()
            nr = 0
            mask = 1
            while gpio >= mask:
                if gpio & mask:
                    r.add(nr)
                nr += 1
                mask *= 2
            return r
        else:
            return {gpio}

    def _decode_ad9858_write(self, message):
        if message.address == 0x41:
            self.selected_dds_channels = self._gpio_to_channels(message.data)
        for dds_channel_nr in self.selected_dds_channels:
            dds_channel = self.dds_channels[dds_channel_nr]
            if message.address in range(0x0a, 0x0e):
                dds_channel["ftw"][message.address - 0x0a] = message.data
            elif message.address in range(0x0e, 0x10):
                dds_channel["pow"][message.address - 0x0e] = message.data
            elif message.address == 0x40:  # FUD
                if None not in dds_channel["ftw"]:
                    ftw = sum(x << i*8
                              for i, x in enumerate(dds_channel["ftw"]))
                    frequency = ftw*self.sysclk/2**32
                    dds_channel["vcd_frequency"].set_value_double(frequency)
                if None not in dds_channel["pow"]:
                    pow = dds_channel["pow"][0] | (dds_channel["pow"][1] & 0x3f) << 8
                    phase = pow/2**14
                    dds_channel["vcd_phase"].set_value_double(phase)

    def _decode_ad9914_write(self, message):
        if message.address == 0x81:
            self.selected_dds_channels = self._gpio_to_channels(message.data)
        for dds_channel_nr in self.selected_dds_channels:
            dds_channel = self.dds_channels[dds_channel_nr]
            if message.address == 0x2d:
                dds_channel["ftw"][0] = message.data
            elif message.address == 0x2f:
                dds_channel["ftw"][1] = message.data
            elif message.address == 0x31:
                dds_channel["pow"] = message.data
            elif message.address == 0x80:  # FUD
                if None not in dds_channel["ftw"]:
                    ftw = sum(x << i*16
                              for i, x in enumerate(dds_channel["ftw"]))
                    frequency = ftw*self.sysclk/2**32
                    dds_channel["vcd_frequency"].set_value_double(frequency)
                if dds_channel["pow"] is not None:
                    phase = dds_channel["pow"]/2**16
                    dds_channel["vcd_phase"].set_value_double(phase)

    def process_message(self, message):
        if isinstance(message, OutputMessage):
            logger.debug("DDS write @%d 0x%04x to 0x%02x, selected channels: %s",
                         message.timestamp, message.data, message.address,
                         self.selected_dds_channels)
            if self.dds_type == "AD9858":
                self._decode_ad9858_write(message)
            elif self.dds_type == "AD9914":
                self._decode_ad9914_write(message)


def _extract_log_chars(data):
    r = ""
    for i in range(4):
        n = data >> 24
        data = (data << 8) & 0xffffffff
        if not n:
            return r
        r += chr(n)
    return r


class LogHandler:
    def __init__(self, vcd_manager, vcd_log_channels):
        self.vcd_channels = dict()
        for name, maxlength in vcd_log_channels.items():
            self.vcd_channels[name] = vcd_manager.get_channel("log/" + name,
                                                              maxlength*8)
        self.current_entry = ""

    def process_message(self, message):
        if isinstance(message, OutputMessage):
            message_payload = _extract_log_chars(message.data)
            self.current_entry += message_payload
            if len(message_payload) < 4:
                channel_name, log_message = \
                    self.current_entry.split(":", maxsplit=1)
                vcd_value = ""
                for c in log_message:
                    vcd_value += "{:08b}".format(ord(c))
                self.vcd_channels[channel_name].set_value(vcd_value)
                self.current_entry = ""


def get_vcd_log_channels(log_channel, messages):
    vcd_log_channels = dict()
    log_entry = ""
    for message in messages:
        if (isinstance(message, OutputMessage)
                and message.channel == log_channel):
            message_payload = _extract_log_chars(message.data)
            log_entry += message_payload
            if len(message_payload) < 4:
                channel_name, log_message = log_entry.split("\x1E", maxsplit=1)
                l = len(log_message)
                if channel_name in vcd_log_channels:
                    if vcd_log_channels[channel_name] < l:
                        vcd_log_channels[channel_name] = l
                else:
                    vcd_log_channels[channel_name] = l
                log_entry = ""
    return vcd_log_channels


def get_single_device_argument(devices, module, cls, argument):
    ref_period = None
    for desc in devices.values():
        if isinstance(desc, dict) and desc["type"] == "local":
            if (desc["module"] == module
                    and desc["class"] == cls):
                if ref_period is None:
                    ref_period = desc["arguments"][argument]
                else:
                    return None  # more than one device found
    return ref_period


def get_ref_period(devices):
    return get_single_device_argument(devices, "artiq.coredevice.core",
                                      "Core", "ref_period")


def get_dds_sysclk(devices):
    return get_single_device_argument(devices, "artiq.coredevice.dds",
                                      "CoreDDS", "sysclk")


def create_channel_handlers(vcd_manager, devices, ref_period,
                            dds_sysclk, dds_onehot_sel):
    channel_handlers = dict()
    for name, desc in sorted(devices.items(), key=itemgetter(0)):
        if isinstance(desc, dict) and desc["type"] == "local":
            if (desc["module"] == "artiq.coredevice.ttl"
                    and desc["class"] in {"TTLOut", "TTLInOut"}):
                channel = desc["arguments"]["channel"]
                channel_handlers[channel] = TTLHandler(vcd_manager, name)
            if (desc["module"] == "artiq.coredevice.ttl"
                    and desc["class"] == "TTLClockGen"):
                channel = desc["arguments"]["channel"]
                channel_handlers[channel] = TTLClockGenHandler(vcd_manager, name, ref_period)
            if (desc["module"] == "artiq.coredevice.dds"
                    and desc["class"] in {"AD9858", "AD9914"}):
                dds_bus_channel = desc["arguments"]["bus_channel"]
                dds_channel = desc["arguments"]["channel"]
                if dds_bus_channel in channel_handlers:
                    dds_handler = channel_handlers[dds_bus_channel]
                    if dds_handler.dds_type != desc["class"]:
                        raise ValueError("All DDS channels must have the same type")
                else:
                    dds_handler = DDSHandler(vcd_manager, desc["class"],
                        dds_onehot_sel, dds_sysclk)
                    channel_handlers[dds_bus_channel] = dds_handler
                dds_handler.add_dds_channel(name, dds_channel)
    return channel_handlers


def get_message_time(message):
    return getattr(message, "timestamp", message.rtio_counter)


def decoded_dump_to_vcd(fileobj, devices, dump):
    vcd_manager = VCDManager(fileobj)
    ref_period = get_ref_period(devices)
    if ref_period is not None:
        vcd_manager.set_timescale_ns(ref_period*1e9)
    else:
        logger.warning("unable to determine core device ref_period")
        ref_period = 1e-9  # guess
    dds_sysclk = get_dds_sysclk(devices)
    if dds_sysclk is None:
        logger.warning("unable to determine DDS sysclk")
        dds_sysclk = 3e9  # guess

    if isinstance(dump.messages[-1], StoppedMessage):
        messages = dump.messages[:-1]
    else:
        logger.warning("StoppedMessage missing")
        messages = dump.messages
    messages = sorted(messages, key=get_message_time)

    channel_handlers = create_channel_handlers(
        vcd_manager, devices, ref_period,
        dds_sysclk, dump.dds_onehot_sel)
    vcd_log_channels = get_vcd_log_channels(dump.log_channel, messages)
    channel_handlers[dump.log_channel] = LogHandler(
        vcd_manager, vcd_log_channels)
    slack = vcd_manager.get_channel("rtio_slack", 64)

    vcd_manager.set_time(0)
    if messages:
        start_time = get_message_time(messages[0])
        for message in messages:
            if message.channel in channel_handlers:
                vcd_manager.set_time(
                    get_message_time(message) - start_time)
                channel_handlers[message.channel].process_message(message)
                if isinstance(message, OutputMessage):
                    slack.set_value_double(
                        (message.timestamp - message.rtio_counter)*ref_period)
