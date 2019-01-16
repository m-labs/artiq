from migen import *
from migen.genlib.record import Record, layout_len
from migen.genlib.fsm import FSM
from misoc.interconnect.csr import *
from misoc.interconnect import stream, wishbone

from artiq.gateware.rtio import cri


def _reverse_bytes(s, g):
    return Cat(reversed(list(s[i*g:(i+1)*g] for i in range(len(s)//g))))


class WishboneReader(Module):
    def __init__(self, bus=None):
        if bus is None:
            bus = wishbone.Interface
        self.bus = bus

        aw = len(bus.adr)
        dw = len(bus.dat_w)
        self.sink = stream.Endpoint([("address", aw)])
        self.source = stream.Endpoint([("data", dw)])

        # # #

        bus_stb = Signal()
        data_reg_loaded = Signal()

        self.comb += [
            bus_stb.eq(self.sink.stb & (~data_reg_loaded | self.source.ack)),
            bus.cyc.eq(bus_stb),
            bus.stb.eq(bus_stb),
            bus.adr.eq(self.sink.address),
            self.sink.ack.eq(bus.ack),
            self.source.stb.eq(data_reg_loaded),
        ]
        self.sync += [
            If(self.source.ack, data_reg_loaded.eq(0)),
            If(bus.ack,
                data_reg_loaded.eq(1),
                self.source.data.eq(bus.dat_r),
                self.source.eop.eq(self.sink.eop)
            )
        ]


class DMAReader(Module, AutoCSR):
    def __init__(self, membus, enable):
        aw = len(membus.adr)
        data_alignment = log2_int(len(membus.dat_w)//8)

        self.submodules.wb_reader = WishboneReader(membus)
        self.source = self.wb_reader.source

        # All numbers in bytes
        self.base_address = CSRStorage(aw + data_alignment,
                                       alignment_bits=data_alignment)

        # # #

        enable_r = Signal()
        address = self.wb_reader.sink
        self.sync += [
            enable_r.eq(enable),
            If(enable & ~enable_r,
                address.address.eq(self.base_address.storage),
                address.eop.eq(0),
                address.stb.eq(1),
            ),
            If(address.stb & address.ack,
                If(address.eop,
                    address.stb.eq(0)
                ).Else(
                    address.address.eq(address.address + 1),
                    If(~enable, address.eop.eq(1))
                )
            )
        ]


class RawSlicer(Module):
    def __init__(self, in_size, out_size, granularity):
        g = granularity

        self.sink = stream.Endpoint([("data", in_size*g)])
        self.source = Signal(out_size*g)
        self.source_stb = Signal()
        self.source_consume = Signal(max=out_size+1)
        self.flush = Signal()
        self.flush_done = Signal()

        # # #

        # worst-case buffer space required (when loading):
        #          <data being shifted out>   <new incoming word>
        buf_size =       out_size - 1       +       in_size
        buf = Signal(buf_size*g)
        self.comb += self.source.eq(buf[:out_size*g])

        level = Signal(max=buf_size+1)
        next_level = Signal(max=buf_size+1)
        self.sync += level.eq(next_level)
        self.comb += next_level.eq(level)

        load_buf = Signal()
        shift_buf = Signal()

        self.sync += [
            If(load_buf, Case(level,
                {i: buf[i*g:(i+in_size)*g].eq(_reverse_bytes(self.sink.data, g))
                 for i in range(out_size)})),
            If(shift_buf, Case(self.source_consume,
                {i: buf.eq(buf[i*g:])
                 for i in range(out_size)})),
        ]

        fsm = FSM(reset_state="FETCH")
        self.submodules += fsm

        fsm.act("FETCH",
            self.sink.ack.eq(1),
            load_buf.eq(1),
            If(self.sink.stb,
                next_level.eq(level + in_size)
            ),
            If(next_level >= out_size, NextState("OUTPUT"))
        )
        fsm.act("OUTPUT",
            self.source_stb.eq(1),
            shift_buf.eq(1),
            next_level.eq(level - self.source_consume),
            If(next_level < out_size, NextState("FETCH")),
            If(self.flush, NextState("FLUSH"))
        )
        fsm.act("FLUSH",
            next_level.eq(0),
            self.sink.ack.eq(1),
            If(self.sink.stb & self.sink.eop,
                self.flush_done.eq(1),
                NextState("FETCH")
            )
        )


# end marker is a record with length=0
record_layout = [
    ("length", 8),  # of whole record (header+data)
    ("channel", 24),
    ("timestamp", 64),
    ("address", 8),
    ("data", 512)  # variable length
]


class RecordConverter(Module):
    def __init__(self, stream_slicer):
        self.source = stream.Endpoint(record_layout)
        self.end_marker_found = Signal()
        self.flush = Signal()

        hdrlen = (layout_len(record_layout) - 512)//8
        record_raw = Record(record_layout)
        self.comb += [
            record_raw.raw_bits().eq(stream_slicer.source),
            self.source.channel.eq(record_raw.channel),
            self.source.timestamp.eq(record_raw.timestamp),
            self.source.address.eq(record_raw.address),
            Case(record_raw.length,
                {hdrlen+i: self.source.data.eq(record_raw.data[:i*8])
                 for i in range(1, 512//8+1)}),
        ]

        fsm = FSM(reset_state="FLOWING")
        self.submodules += fsm

        fsm.act("FLOWING",
            If(stream_slicer.source_stb,
                If(record_raw.length == 0,
                    NextState("END_MARKER_FOUND")
                ).Else(
                    self.source.stb.eq(1)
                )
            ),
            If(self.source.ack,
                stream_slicer.source_consume.eq(record_raw.length)
            )
        )
        fsm.act("END_MARKER_FOUND",
            self.end_marker_found.eq(1),
            If(self.flush,
                stream_slicer.flush.eq(1),
                NextState("WAIT_FLUSH")
            )
        )
        fsm.act("WAIT_FLUSH",
            If(stream_slicer.flush_done,
                NextState("SEND_EOP")
            )
        )
        fsm.act("SEND_EOP",
            self.source.eop.eq(1),
            self.source.stb.eq(1),
            If(self.source.ack, NextState("FLOWING"))
        )


class RecordSlicer(Module):
    def __init__(self, in_size):
        self.submodules.raw_slicer = ResetInserter()(RawSlicer(
            in_size//8, layout_len(record_layout)//8, 8))
        self.submodules.record_converter = RecordConverter(self.raw_slicer)

        self.end_marker_found = self.record_converter.end_marker_found
        self.flush = self.record_converter.flush

        self.sink = self.raw_slicer.sink
        self.source = self.record_converter.source


class TimeOffset(Module, AutoCSR):
    def __init__(self):
        self.time_offset = CSRStorage(64)
        self.source = stream.Endpoint(record_layout)
        self.sink = stream.Endpoint(record_layout)

        # # #

        self.sync += [
            If(self.source.ack, self.source.stb.eq(0)),
            If(~self.source.stb,
                self.sink.payload.connect(self.source.payload,
                                          omit={"timestamp"}),
                self.source.payload.timestamp.eq(self.sink.payload.timestamp
                                                 + self.time_offset.storage),
                self.source.eop.eq(self.sink.eop),
                self.source.stb.eq(self.sink.stb)
            )
        ]
        self.comb += self.sink.ack.eq(~self.source.stb)


class CRIMaster(Module, AutoCSR):
    def __init__(self):
        self.error = CSR(2)

        self.error_channel = CSRStatus(24)
        self.error_timestamp = CSRStatus(64)
        self.error_address = CSRStatus(16)

        self.sink = stream.Endpoint(record_layout)
        self.cri = cri.Interface()
        self.busy = Signal()

        # # #

        underflow_trigger = Signal()
        link_error_trigger = Signal()
        self.sync += [
            If(underflow_trigger,
                self.error.w.eq(1),
                self.error_channel.status.eq(self.sink.channel),
                self.error_timestamp.status.eq(self.sink.timestamp),
                self.error_address.status.eq(self.sink.address)
            ),
            If(link_error_trigger,
                self.error.w.eq(2),
                self.error_channel.status.eq(self.sink.channel),
                self.error_timestamp.status.eq(self.sink.timestamp),
                self.error_address.status.eq(self.sink.address)
            ),
            If(self.error.re, self.error.w.eq(0))
        ]

        self.comb += [
            self.cri.chan_sel.eq(self.sink.channel),
            self.cri.o_timestamp.eq(self.sink.timestamp),
            self.cri.o_address.eq(self.sink.address),
            self.cri.o_data.eq(self.sink.data)
        ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.error.w == 0,
                If(self.sink.stb,
                    If(self.sink.eop,
                        # last packet contains dummy data, discard it
                        self.sink.ack.eq(1)
                    ).Else(
                        NextState("WRITE")
                    )
                )
            ).Else(
                # discard all data until errors are acked
                self.sink.ack.eq(1)
            )
        )
        fsm.act("WRITE",
            self.busy.eq(1),
            self.cri.cmd.eq(cri.commands["write"]),
            NextState("CHECK_STATE")
        )
        fsm.act("CHECK_STATE",
            self.busy.eq(1),
            If(self.cri.o_status == 0,
                self.sink.ack.eq(1),
                NextState("IDLE")
            ),
            If(self.cri.o_status[1], NextState("UNDERFLOW")),
            If(self.cri.o_status[2], NextState("LINK_ERROR"))
        )
        fsm.act("UNDERFLOW",
            self.busy.eq(1),
            underflow_trigger.eq(1),
            self.sink.ack.eq(1),
            NextState("IDLE")
        )
        fsm.act("LINK_ERROR",
            self.busy.eq(1),
            link_error_trigger.eq(1),
            self.sink.ack.eq(1),
            NextState("IDLE")
        )


class DMA(Module):
    def __init__(self, membus):
        self.enable = CSR()

        flow_enable = Signal()
        self.submodules.dma = DMAReader(membus, flow_enable)
        self.submodules.slicer = RecordSlicer(len(membus.dat_w))
        self.submodules.time_offset = TimeOffset()
        self.submodules.cri_master = CRIMaster()
        self.cri = self.cri_master.cri

        self.comb += [
            self.dma.source.connect(self.slicer.sink),
            self.slicer.source.connect(self.time_offset.sink),
            self.time_offset.source.connect(self.cri_master.sink)
        ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.enable.re, NextState("FLOWING"))
        )
        fsm.act("FLOWING",
            self.enable.w.eq(1),
            flow_enable.eq(1),
            If(self.slicer.end_marker_found,
                NextState("FLUSH")
            )
        )
        fsm.act("FLUSH",
            self.enable.w.eq(1),
            self.slicer.flush.eq(1),
            NextState("WAIT_EOP")
        )
        fsm.act("WAIT_EOP",
            self.enable.w.eq(1),
            If(self.cri_master.sink.stb & self.cri_master.sink.ack & self.cri_master.sink.eop,
                NextState("WAIT_CRI_MASTER")
            )
        )
        fsm.act("WAIT_CRI_MASTER",
            self.enable.w.eq(1),
            If(~self.cri_master.busy, NextState("IDLE"))
        )

    def get_csrs(self):
        return ([self.enable] +
                self.dma.get_csrs() + self.time_offset.get_csrs() +
                self.cri_master.get_csrs())
