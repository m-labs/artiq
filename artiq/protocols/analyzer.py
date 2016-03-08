from enum import Enum


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
    o_collision_reset = 0b010010

    i_overflow_reset = 0b100000
