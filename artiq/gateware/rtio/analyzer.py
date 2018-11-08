from migen import *
from migen.genlib.record import Record, layout_len
from misoc.interconnect.csr import *
from misoc.interconnect import stream

from artiq.gateware.rtio.cri import commands as cri_commands
from artiq.coredevice.comm_analyzer import MessageType, ExceptionType


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
    def __init__(self, tsc, cri, enable):
        self.source = stream.Endpoint([("data", message_len)])

        self.overflow = CSRStatus()
        self.overflow_reset = CSR()

        # # #

        read_wait_event = cri.i_status[2]
        read_wait_event_r = Signal()
        read_done = Signal()
        read_overflow = Signal()
        self.sync += read_wait_event_r.eq(read_wait_event)
        self.comb += \
            If(read_wait_event_r & ~read_wait_event,
                If(~cri.i_status[0], read_done.eq(1)),
                If(cri.i_status[1], read_overflow.eq(1))
            )

        input_output_stb = Signal()
        input_output = Record(input_output_layout)
        self.comb += [
            input_output.channel.eq(cri.chan_sel),
            input_output.address_padding.eq(cri.o_address),
            input_output.rtio_counter.eq(tsc.full_ts_cri),
            If(cri.cmd == cri_commands["write"],
                input_output.message_type.eq(MessageType.output.value),
                input_output.timestamp.eq(cri.o_timestamp),
                input_output.data.eq(cri.o_data)
            ).Else(
                input_output.message_type.eq(MessageType.input.value),
                input_output.timestamp.eq(cri.i_timestamp),
                input_output.data.eq(cri.i_data)
            ),
            input_output_stb.eq((cri.cmd == cri_commands["write"]) | read_done)
        ]

        exception_stb = Signal()
        exception = Record(exception_layout)
        self.comb += [
            exception.message_type.eq(MessageType.exception.value),
            exception.channel.eq(cri.chan_sel),
            exception.rtio_counter.eq(tsc.full_ts_cri),
        ]
        just_written = Signal()
        self.sync += just_written.eq(cri.cmd == cri_commands["write"])
        self.comb += [
            If(just_written & cri.o_status[1],
                exception_stb.eq(1),
                exception.exception_type.eq(ExceptionType.o_underflow.value)
            ),
            If(read_overflow,
                exception_stb.eq(1),
                exception.exception_type.eq(ExceptionType.i_overflow.value)
            )
        ]

        stopped = Record(stopped_layout)
        self.comb += [
            stopped.message_type.eq(MessageType.stopped.value),
            stopped.rtio_counter.eq(tsc.full_ts_cri),
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
        self.byte_count = CSRStatus(64)  # only read when shut down

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

        message_count = Signal(64 - log2_int(message_len//8))
        self.comb += self.byte_count.status.eq(
            message_count << log2_int(message_len//8))
        self.sync += [
            If(self.reset.re, message_count.eq(0)),
            If(membus.ack, message_count.eq(
                message_count + self.sink.valid_token_count))
        ]


class Analyzer(Module, AutoCSR):
    def __init__(self, tsc, cri, membus, fifo_depth=128):
        # shutdown procedure: set enable to 0, wait until busy=0
        self.enable = CSRStorage()
        self.busy = CSRStatus()

        self.submodules.message_encoder = MessageEncoder(
            tsc, cri, self.enable.storage)
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
