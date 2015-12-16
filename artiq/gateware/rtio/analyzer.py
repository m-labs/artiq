from migen import *
from migen.genlib.record import Record, layout_len
from misoc.interconnect.csr import *
from misoc.interconnect import stream


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
        self.source = stream.Endpoint([("data", 256)])

        self.message_types = MessageTypes()
        self.exception_types = ExceptionTypes()

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
                self.source.data.eq(exception.raw_bits())
            ).Else(
                self.source.data.eq(input_output.raw_bits())
            ),
            self.source.stb.eq(input_output_stb | exception_stb)
        ]

        self.sync += [
            If(self.overflow_reset.re, self.overflow.status.eq(0)),
            If(self.source.stb & ~self.source.ack,
                self.overflow.status.eq(1)
            )
        ]


class DMAWriter(Module, AutoCSR):
    def __init__(self, membus):
        aw = len(membus.adr)
        dw = len(membus.dat_w)
        data_alignment = log2_int(dw//8)

        # shutdown procedure: set enable to 0, wait until busy=0
        self.enable = CSRStorage()
        self.busy = CSRStatus()
        self.reset = CSR()  # only apply when shut down
        # All numbers in bytes
        self.base_address = CSRStorage(aw + data_alignment,
                                       alignment_bits=data_alignment)
        self.last_address = CSRStorage(aw + data_alignment,
                                       alignment_bits=data_alignment)
        self.byte_count = CSRStatus(64)  # only read when shut down

        self.sink = stream.Endpoint([("data", dw)])

        # # #

        event_counter = Signal(63)
        self.comb += self.byte_count.status.eq(
            event_counter << data_alignment)

        fsm = FSM()
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.enable.storage & self.sink.stb,
                NextState("WRITE")
            ),
            If(~self.enable.storage,
                self.sink.ack.eq(1)
            ),
            If(self.reset.re,
                NextValue(membus.adr, self.base_address.storage),
                NextValue(event_counter, 0)
            )
        )
        fsm.act("WRITE",
            self.busy.status.eq(1),

            membus.cyc.eq(1),
            membus.stb.eq(1),
            membus.we.eq(1),
            membus.sel.eq(2**len(membus.sel)-1),

            If(membus.ack,
                If(membus.adr == self.last_address.storage,
                    NextValue(membus.adr, self.base_address.storage)
                ).Else(
                    NextValue(membus.adr, membus.adr + 1)
                ),
                NextValue(event_counter, event_counter + 1),
                self.sink.ack.eq(1),
                NextState("IDLE")
            )
        )


class Analyzer(Module, AutoCSR):
    def __init__(self, rtio_core, membus, fifo_depth=128):
        dw = len(membus.dat_w)

        self.submodules.message_encoder = MessageEncoder(rtio_core)
        self.submodules.converter = stream.Converter(
            [("data", 256)], [("data", dw)])
        self.submodules.fifo = stream.SyncFIFO(
            [("data", dw)], fifo_depth, True)
        self.submodules.dma = DMAWriter(membus)

        self.comb += [
            self.message_encoder.source.connect(self.converter.sink),
            self.converter.source.connect(self.fifo.sink),
            self.fifo.source.connect(self.dma.sink)
        ]
