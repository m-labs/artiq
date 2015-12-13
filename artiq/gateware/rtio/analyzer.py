from migen import *
from migen.genlib.record import Record, layout_len
from misoc.interconnect.csr import *


__all__ = ["Analyzer"]


input_output_layout = [
    ("message_type", 2),
    ("channel", 30),
    ("timestamp", 64),
    ("rtio_counter", 64),
    ("address_padding", 32),
    ("data", 64)
]

exception_layout = [
    ("message_type", 2),
    ("channel", 30),
    ("padding", 64),
    ("rtio_counter", 64),
    ("exception_type", 8),
    ("padding", 88)
]

assert layout_len(input_output_layout) == 256
assert layout_len(exception_layout) == 256


class MessageTypes(AutoCSR):
    def __init__(self):
        self.output = CSRConstant(0b00)
        self.input = CSRConstant(0b01)
        self.exception = CSRConstant(0b10)


class ExceptionTypes(AutoCSR):
    def __init__(self):
        self.reset_rising = CSRConstant(0b000000)
        self.reset_falling = CSRConstant(0b000001)
        self.reset_phy_rising = CSRConstant(0b000010)
        self.reset_phy_falling = CSRConstant(0b000011)

        self.o_underflow_reset = CSRConstant(0b010000)
        self.o_sequence_error_reset = CSRConstant(0b010001)
        self.o_collision_error_reset = CSRConstant(0b010010)

        self.i_overflow_reset = CSRConstant(0b100000)


class MessageEncoder(Module, AutoCSR):
    def __init__(self, rtio_core):
        self.message = Signal(256)
        self.stb = Signal()

        self.message_types = MessageTypes()
        self.exception_types = ExceptionTypes()

        # # #

        kcsrs = rtio_core.kcsrs

        input_output_stb = Signal()
        input_output = Record(input_output_layout)
        if hasattr(kcsrs, "o_data"):
            o_data = kcsrs.o_data.storage
        else:
            o_data = 0
        if hasattr(kcsrs, "o_address"):
            o_address = kcsrs.o_address.storage
        else:
            o_address = 0
        if hasattr(kcsrs, "i_data"):
            i_data = kcsrs.i_data
        else:
            i_data = 0
        self.comb += [
            input_output.channel.eq(kcsrs.chan_sel.storage),
            input_output.address_padding.eq(o_address),
            input_output.rtio_counter.eq(
                rtio_core.counter.value_sys << rtio_core.fine_ts_width),
            If(kcsrs.o_we.re,
                input_output.message_type.eq(self.message_types.output.value),
                input_output.timestamp.eq(kcsrs.o_timestamp.storage),
                input_output.data.eq(o_data)
            ).Else(
                input_output.message_type.eq(self.message_types.input.value),
                input_output.timestamp.eq(kcsrs.i_timestamp.status),
                input_output.data.eq(i_data)
            ),
            input_output_stb.eq(kcsrs.o_we.re | kcsrs.i_re.re)
        ]

        exception_stb = Signal()
        exception = Record(exception_layout)
        self.comb += [
            exception.message_type.eq(self.message_types.exception.value),
            exception.channel.eq(kcsrs.chan_sel.storage),
            exception.rtio_counter.eq(
                rtio_core.counter.value_sys << rtio_core.fine_ts_width),
        ]
        for ename in ("o_underflow_reset", "o_sequence_error_reset",
                      "o_collision_error_reset", "i_overflow_reset"):
            self.comb += \
                If(getattr(kcsrs, ename).re,
                    exception_stb.eq(1),
                    exception.exception_type.eq(
                        getattr(self.exception_types, ename).value)
                )
        for rname in "reset", "reset_phy":
            r_d = Signal()
            r = getattr(kcsrs, rname).storage
            self.sync += r_d.eq(r)
            self.comb += [
                If(r & ~r_d,
                    exception_stb.eq(1),
                    exception.exception_type.eq(
                        getattr(self.exception_types, rname+"_rising").value)
                ),
                If(~r & r_d,
                    exception_stb.eq(1),
                    exception.exception_type.eq(
                        getattr(self.exception_types, rname+"_falling").value)
                )
            ]

        self.sync += [
            If(exception_stb,
                self.message.eq(exception.raw_bits())
            ).Else(
                self.message.eq(input_output.raw_bits())
            ),
            self.stb.eq(input_output_stb | exception_stb)
        ]


class Analyzer(Module):
    def __init__(self, rtio_core):
        pass
