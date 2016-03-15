from migen import *
from migen.genlib.record import Record, layout_len
from misoc.interconnect.csr import *
from misoc.interconnect import stream

from artiq.protocols.analyzer import MessageType, ExceptionType


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
    ("padding0", 64),
    ("rtio_counter", 64),
    ("exception_type", 8),
    ("padding1", 88)
]

stopped_layout = [
    ("message_type", 2),
    ("padding0", 94),
    ("rtio_counter", 64),
    ("padding1", 96)
]

message_len = 256

assert layout_len(input_output_layout) == message_len
assert layout_len(exception_layout) == message_len
assert layout_len(stopped_layout) == message_len


class MessageEncoder(Module, AutoCSR):
    def __init__(self, rtio_core, enable):
        self.source = stream.Endpoint([("data", message_len)])

        self.overflow = CSRStatus()
        self.overflow_reset = CSR()

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
            i_data = kcsrs.i_data.status
        else:
            i_data = 0
        self.comb += [
            input_output.channel.eq(kcsrs.chan_sel.storage),
            input_output.address_padding.eq(o_address),
            input_output.rtio_counter.eq(
                rtio_core.counter.value_sys << rtio_core.fine_ts_width),
            If(kcsrs.o_we.re,
                input_output.message_type.eq(MessageType.output.value),
                input_output.timestamp.eq(kcsrs.o_timestamp.storage),
                input_output.data.eq(o_data)
            ).Else(
                input_output.message_type.eq(MessageType.input.value),
                input_output.timestamp.eq(kcsrs.i_timestamp.status),
                input_output.data.eq(i_data)
            ),
            input_output_stb.eq(kcsrs.o_we.re | kcsrs.i_re.re)
        ]

        exception_stb = Signal()
        exception = Record(exception_layout)
        self.comb += [
            exception.message_type.eq(MessageType.exception.value),
            exception.channel.eq(kcsrs.chan_sel.storage),
            exception.rtio_counter.eq(
                rtio_core.counter.value_sys << rtio_core.fine_ts_width),
        ]
        for ename in ("o_underflow_reset", "o_sequence_error_reset",
                      "o_collision_reset", "i_overflow_reset"):
            self.comb += \
                If(getattr(kcsrs, ename).re,
                    exception_stb.eq(1),
                    exception.exception_type.eq(
                        getattr(ExceptionType, ename).value)
                )
        for rname in "reset", "reset_phy":
            r_d = Signal(reset=1)
            r = getattr(kcsrs, rname).storage
            self.sync += r_d.eq(r)
            self.comb += [
                If(r & ~r_d,
                    exception_stb.eq(1),
                    exception.exception_type.eq(
                        getattr(ExceptionType, rname+"_rising").value)
                ),
                If(~r & r_d,
                    exception_stb.eq(1),
                    exception.exception_type.eq(
                        getattr(ExceptionType, rname+"_falling").value)
                )
            ]

        stopped = Record(stopped_layout)
        self.comb += [
            stopped.message_type.eq(MessageType.stopped.value),
            stopped.rtio_counter.eq(
                rtio_core.counter.value_sys << rtio_core.fine_ts_width),
        ]

        enable_r = Signal()
        stopping = Signal()
        self.sync += [
            enable_r.eq(enable),
            If(~enable & enable_r, stopping.eq(1)),

            If(~stopping,
                If(exception_stb,
                    self.source.data.eq(exception.raw_bits())
                ).Else(
                    self.source.data.eq(input_output.raw_bits())
                ),
                self.source.eop.eq(0),
                self.source.stb.eq(enable &
                                  (input_output_stb | exception_stb)),

                If(self.overflow_reset.re, self.overflow.status.eq(0)),
                If(self.source.stb & ~self.source.ack,
                    self.overflow.status.eq(1)
                )
            ).Else(
                self.source.data.eq(stopped.raw_bits()),
                self.source.eop.eq(1),
                self.source.stb.eq(1),
                If(self.source.ack, stopping.eq(0))
            )
        ]


class DMAWriter(Module, AutoCSR):
    def __init__(self, membus):
        aw = len(membus.adr)
        dw = len(membus.dat_w)
        messages_per_dw = dw//message_len
        data_alignment = log2_int(dw//8)

        self.reset = CSR()  # only apply when shut down
        # All numbers in bytes
        self.base_address = CSRStorage(aw + data_alignment,
                                       alignment_bits=data_alignment)
        self.last_address = CSRStorage(aw + data_alignment,
                                       alignment_bits=data_alignment)
        self.byte_count = CSRStatus(32)  # only read when shut down

        self.sink = stream.Endpoint(
            [("data", dw),
             ("valid_token_count", bits_for(messages_per_dw))])

        # # #

        self.comb += [
            membus.cyc.eq(self.sink.stb),
            membus.stb.eq(self.sink.stb),
            self.sink.ack.eq(membus.ack),
            membus.we.eq(1),
            membus.dat_w.eq(self.sink.data)
        ]
        if messages_per_dw > 1:
            for i in range(dw//8):
                self.comb += membus.sel[i].eq(
                    self.sink.valid_token_count >= i//(256//8))
        else:
            self.comb += membus.sel.eq(2**(dw//8)-1)

        self.sync += [
            If(self.reset.re,
                membus.adr.eq(self.base_address.storage)),
            If(membus.ack,
                If(membus.adr == self.last_address.storage,
                    membus.adr.eq(self.base_address.storage)
                ).Else(
                    membus.adr.eq(membus.adr + 1)
                ),
            )
        ]

        message_count = Signal(32 - log2_int(message_len//8))
        self.comb += self.byte_count.status.eq(
            message_count << log2_int(message_len//8))
        self.sync += [
            If(self.reset.re, message_count.eq(0)),
            If(membus.ack, message_count.eq(
                message_count + self.sink.valid_token_count))
        ]


class Analyzer(Module, AutoCSR):
    def __init__(self, rtio_core, membus, fifo_depth=128):
        # shutdown procedure: set enable to 0, wait until busy=0
        self.enable = CSRStorage()
        self.busy = CSRStatus()

        self.submodules.message_encoder = MessageEncoder(
            rtio_core, self.enable.storage)
        self.submodules.fifo = stream.SyncFIFO(
            [("data", message_len)], fifo_depth, True)
        self.submodules.converter = stream.Converter(
            message_len, len(membus.dat_w), reverse=True,
            report_valid_token_count=True)
        self.submodules.dma = DMAWriter(membus)

        enable_r = Signal()
        self.sync += [
            enable_r.eq(self.enable.storage),
            If(self.enable.storage & ~enable_r,
                self.busy.status.eq(1)),
            If(self.dma.sink.stb & self.dma.sink.ack & self.dma.sink.eop,
                self.busy.status.eq(0))
        ]

        self.comb += [
            self.message_encoder.source.connect(self.fifo.sink),
            self.fifo.source.connect(self.converter.sink),
            self.converter.source.connect(self.dma.sink)
        ]
