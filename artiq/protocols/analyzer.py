from enum import Enum


class MessageType(Enum):
    output = 0b00
    input = 0b01
    exception = 0b10
    stopped = 0b11


class ExceptionType(Enum):
    legacy_reset = 0b000000
    legacy_reset_falling = 0b000001
    legacy_reset_phy = 0b000010
    legacy_reset_phy_falling = 0b000011

    o_underflow_reset = 0b010000
    o_sequence_error_reset = 0b010001
    o_collision_reset = 0b010010

    i_overflow_reset = 0b100000
