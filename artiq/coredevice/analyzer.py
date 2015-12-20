from enum import Enum
from collections import namedtuple
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
    parts = struct.unpack(">IQI", data[:16])
    sent_bytes, total_byte_count, overflow_occured = parts

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

