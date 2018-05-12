"""
Etherbone

CERN's Etherbone protocol is initially used to run a Wishbone bus over an
ethernet network. This re-implementation is meant to be run over serdes
and introduces some limitations:
- no probing (pf/pr)
- no address spaces (rca/bca/wca/wff)
- 32bits data and address
- 1 record per frame
"""

from migen import *

from misoc.interconnect import stream
from misoc.interconnect import wishbone

from artiq.gateware.serwb.packet import *


class _Packetizer(Module):
    def __init__(self, sink_description, source_description, header):
        self.sink = sink = stream.Endpoint(sink_description)
        self.source = source = stream.Endpoint(source_description)
        self.header = Signal(header.length*8)

        # # #

        dw = len(self.sink.data)

        header_reg = Signal(header.length*8, reset_less=True)
        header_words = (header.length*8)//dw
        load = Signal()
        shift = Signal()
        counter = Signal(max=max(header_words, 2))
        counter_reset = Signal()
        counter_ce = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )

        self.comb += header.encode(sink, self.header)
        if header_words == 1:
            self.sync += [
                If(load,
                    header_reg.eq(self.header)
                )
            ]
        else:
            self.sync += [
                If(load,
                    header_reg.eq(self.header)
                ).Elif(shift,
                    header_reg.eq(Cat(header_reg[dw:], Signal(dw)))
                )
            ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        if header_words == 1:
            idle_next_state = "COPY"
        else:
            idle_next_state = "SEND_HEADER"

        fsm.act("IDLE",
            sink.ack.eq(1),
            counter_reset.eq(1),
            If(sink.stb,
                sink.ack.eq(0),
                source.stb.eq(1),
                source.eop.eq(0),
                source.data.eq(self.header[:dw]),
                If(source.stb & source.ack,
                    load.eq(1),
                    NextState(idle_next_state)
                )
            )
        )
        if header_words != 1:
            fsm.act("SEND_HEADER",
                source.stb.eq(1),
                source.eop.eq(0),
                source.data.eq(header_reg[dw:2*dw]),
                If(source.stb & source.ack,
                    shift.eq(1),
                    counter_ce.eq(1),
                    If(counter == header_words-2,
                        NextState("COPY")
                    )
                )
            )
        if hasattr(sink, "error"):
            self.comb += source.error.eq(sink.error)
        fsm.act("COPY",
            source.stb.eq(sink.stb),
            source.eop.eq(sink.eop),
            source.data.eq(sink.data),
            If(source.stb & source.ack,
                sink.ack.eq(1),
                If(source.eop,
                    NextState("IDLE")
                )
            )
        )


class _Depacketizer(Module):
    def __init__(self, sink_description, source_description, header):
        self.sink = sink = stream.Endpoint(sink_description)
        self.source = source = stream.Endpoint(source_description)
        self.header = Signal(header.length*8)

        # # #

        dw = len(sink.data)

        header_reg = Signal(header.length*8, reset_less=True)
        header_words = (header.length*8)//dw

        shift = Signal()
        counter = Signal(max=max(header_words, 2))
        counter_reset = Signal()
        counter_ce = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )

        if header_words == 1:
            self.sync += \
                If(shift,
                    header_reg.eq(sink.data)
                )
        else:
            self.sync += \
                If(shift,
                    header_reg.eq(Cat(header_reg[dw:], sink.data))
                )
        self.comb += self.header.eq(header_reg)

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        if header_words == 1:
            idle_next_state = "COPY"
        else:
            idle_next_state = "RECEIVE_HEADER"

        fsm.act("IDLE",
            sink.ack.eq(1),
            counter_reset.eq(1),
            If(sink.stb,
                shift.eq(1),
                NextState(idle_next_state)
            )
        )
        if header_words != 1:
            fsm.act("RECEIVE_HEADER",
                sink.ack.eq(1),
                If(sink.stb,
                    counter_ce.eq(1),
                    shift.eq(1),
                    If(counter == header_words-2,
                        NextState("COPY")
                    )
                )
            )
        no_payload = Signal()
        self.sync += \
            If(fsm.before_entering("COPY"),
                no_payload.eq(sink.eop)
            )

        if hasattr(sink, "error"):
            self.comb += source.error.eq(sink.error)
        self.comb += [
            source.eop.eq(sink.eop | no_payload),
            source.data.eq(sink.data),
            header.decode(self.header, source)
        ]
        fsm.act("COPY",
            sink.ack.eq(source.ack),
            source.stb.eq(sink.stb | no_payload),
            If(source.stb & source.ack & source.eop,
                NextState("IDLE")
            )
        )


etherbone_magic = 0x4e6f
etherbone_version = 1
etherbone_packet_header_length = 8
etherbone_packet_header_fields = {
    "magic":     HeaderField(0, 0, 16),

    "version":   HeaderField(2, 4,  4),
    "nr":        HeaderField(2, 2,  1),
    "pr":        HeaderField(2, 1,  1), # unused
    "pf":        HeaderField(2, 0,  1), # unused

    "addr_size": HeaderField(3, 4,  4), # static
    "port_size": HeaderField(3, 0,  4)  # static
}
etherbone_packet_header = Header(etherbone_packet_header_fields,
                                 etherbone_packet_header_length,
                                 swap_field_bytes=True)

etherbone_record_header_length = 4
etherbone_record_header_fields = {
    "bca":         HeaderField(0, 0, 1), # unused
    "rca":         HeaderField(0, 1, 1), # unused
    "rff":         HeaderField(0, 2, 1), # unused
    "cyc":         HeaderField(0, 4, 1), # unused
    "wca":         HeaderField(0, 5, 1), # unused
    "wff":         HeaderField(0, 6, 1), # unused

    "byte_enable": HeaderField(1, 0, 8),

    "wcount":      HeaderField(2, 0, 8),

    "rcount":      HeaderField(3, 0, 8)
}
etherbone_record_header = Header(etherbone_record_header_fields,
                                 etherbone_record_header_length,
                                 swap_field_bytes=True)

def _remove_from_layout(layout, *args):
    r = []
    for f in layout:
        remove = False
        for arg in args:
            if f[0] == arg:
                remove = True
        if not remove:
            r.append(f)
    return r

def etherbone_packet_description(dw):
    layout = etherbone_packet_header.get_layout()
    layout += [("data", dw)]
    return stream.EndpointDescription(layout)

def etherbone_packet_user_description(dw):
    layout = etherbone_packet_header.get_layout()
    layout = _remove_from_layout(layout,
                                 "magic",
                                 "portsize",
                                 "addrsize",
                                 "version")
    layout += user_description(dw).payload_layout
    return stream.EndpointDescription(layout)

def etherbone_record_description(dw):
    layout = etherbone_record_header.get_layout()
    layout += [("data", dw)]
    return stream.EndpointDescription(layout)

def etherbone_mmap_description(dw):
    layout = [
        ("we", 1),
        ("count", 8),
        ("base_addr", 32),
        ("be", dw//8),
        ("addr", 32),
        ("data", dw)
    ]
    return stream.EndpointDescription(layout)


# etherbone packet

class _EtherbonePacketPacketizer(_Packetizer):
    def __init__(self):
        _Packetizer.__init__(self,
            etherbone_packet_description(32),
            user_description(32),
            etherbone_packet_header)


class _EtherbonePacketTX(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint(etherbone_packet_user_description(32))
        self.source = source = stream.Endpoint(user_description(32))

        # # #

        self.submodules.packetizer = packetizer = _EtherbonePacketPacketizer()
        self.comb += [
            packetizer.sink.stb.eq(sink.stb),
            packetizer.sink.eop.eq(sink.eop),
            sink.ack.eq(packetizer.sink.ack),

            packetizer.sink.magic.eq(etherbone_magic),
            packetizer.sink.port_size.eq(32//8),
            packetizer.sink.addr_size.eq(32//8),
            packetizer.sink.nr.eq(sink.nr),
            packetizer.sink.version.eq(etherbone_version),

            packetizer.sink.data.eq(sink.data)
        ]
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            packetizer.source.ack.eq(1),
            If(packetizer.source.stb,
                packetizer.source.ack.eq(0),
                NextState("SEND")
            )
        )
        fsm.act("SEND",
            packetizer.source.connect(source),
            source.length.eq(sink.length + etherbone_packet_header.length),
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )


class _EtherbonePacketDepacketizer(_Depacketizer):
    def __init__(self):
        _Depacketizer.__init__(self,
            user_description(32),
            etherbone_packet_description(32),
            etherbone_packet_header)


class _EtherbonePacketRX(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint(user_description(32))
        self.source = source = stream.Endpoint(etherbone_packet_user_description(32))

        # # #

        self.submodules.depacketizer = depacketizer = _EtherbonePacketDepacketizer()
        self.comb += sink.connect(depacketizer.sink)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            depacketizer.source.ack.eq(1),
            If(depacketizer.source.stb,
                depacketizer.source.ack.eq(0),
                NextState("CHECK")
            )
        )
        stb = Signal()
        self.sync += stb.eq(
            depacketizer.source.stb &
            (depacketizer.source.magic == etherbone_magic)
        )
        fsm.act("CHECK",
            If(stb,
                NextState("PRESENT")
            ).Else(
                NextState("DROP")
            )
        )
        self.comb += [
            source.eop.eq(depacketizer.source.eop),

            source.nr.eq(depacketizer.source.nr),

            source.data.eq(depacketizer.source.data),

            source.length.eq(sink.length - etherbone_packet_header.length)
        ]
        fsm.act("PRESENT",
            source.stb.eq(depacketizer.source.stb),
            depacketizer.source.ack.eq(source.ack),
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )
        fsm.act("DROP",
            depacketizer.source.ack.eq(1),
            If(depacketizer.source.stb &
               depacketizer.source.eop &
               depacketizer.source.ack,
                NextState("IDLE")
            )
        )


class _EtherbonePacket(Module):
    def __init__(self, port_sink, port_source):
        self.submodules.tx = tx = _EtherbonePacketTX()
        self.submodules.rx = rx = _EtherbonePacketRX()
        self.comb += [
            tx.source.connect(port_sink),
            port_source.connect(rx.sink)
        ]
        self.sink, self.source = self.tx.sink, self.rx.source

# etherbone record

class _EtherboneRecordPacketizer(_Packetizer):
    def __init__(self):
        _Packetizer.__init__(self,
            etherbone_record_description(32),
            etherbone_packet_user_description(32),
            etherbone_record_header)


class _EtherboneRecordDepacketizer(_Depacketizer):
    def __init__(self):
        _Depacketizer.__init__(self,
            etherbone_packet_user_description(32),
            etherbone_record_description(32),
            etherbone_record_header)


class _EtherboneRecordReceiver(Module):
    def __init__(self, buffer_depth=4):
        self.sink = sink = stream.Endpoint(etherbone_record_description(32))
        self.source = source = stream.Endpoint(etherbone_mmap_description(32))

        # # #

        fifo = stream.SyncFIFO(etherbone_record_description(32), buffer_depth,
                               buffered=True)
        self.submodules += fifo
        self.comb += sink.connect(fifo.sink)

        base_addr = Signal(32)
        base_addr_update = Signal()
        self.sync += If(base_addr_update, base_addr.eq(fifo.source.data))

        counter = Signal(max=512)
        counter_reset = Signal()
        counter_ce = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            fifo.source.ack.eq(1),
            counter_reset.eq(1),
            If(fifo.source.stb,
                base_addr_update.eq(1),
                If(fifo.source.wcount,
                    NextState("RECEIVE_WRITES")
                ).Elif(fifo.source.rcount,
                    NextState("RECEIVE_READS")

                )
            )
        )
        fsm.act("RECEIVE_WRITES",
            source.stb.eq(fifo.source.stb),
            source.eop.eq(counter == fifo.source.wcount-1),
            source.count.eq(fifo.source.wcount),
            source.be.eq(fifo.source.byte_enable),
            source.addr.eq(base_addr[2:] + counter),
            source.we.eq(1),
            source.data.eq(fifo.source.data),
            fifo.source.ack.eq(source.ack),
            If(source.stb & source.ack,
                counter_ce.eq(1),
                If(source.eop,
                    If(fifo.source.rcount,
                        NextState("RECEIVE_BASE_RET_ADDR")
                    ).Else(
                        NextState("IDLE")
                    )
                )
            )
        )
        fsm.act("RECEIVE_BASE_RET_ADDR",
            counter_reset.eq(1),
            If(fifo.source.stb,
                base_addr_update.eq(1),
                NextState("RECEIVE_READS")
            )
        )
        fsm.act("RECEIVE_READS",
            source.stb.eq(fifo.source.stb),
            source.eop.eq(counter == fifo.source.rcount-1),
            source.count.eq(fifo.source.rcount),
            source.base_addr.eq(base_addr),
            source.addr.eq(fifo.source.data[2:]),
            fifo.source.ack.eq(source.ack),
            If(source.stb & source.ack,
                counter_ce.eq(1),
                If(source.eop,
                    NextState("IDLE")
                )
            )
        )


class _EtherboneRecordSender(Module):
    def __init__(self, buffer_depth=4):
        self.sink = sink = stream.Endpoint(etherbone_mmap_description(32))
        self.source = source = stream.Endpoint(etherbone_record_description(32))

        # # #

        pbuffer = stream.SyncFIFO(etherbone_mmap_description(32), buffer_depth,
                                  buffered=True)
        self.submodules += pbuffer
        self.comb += sink.connect(pbuffer.sink)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            pbuffer.source.ack.eq(1),
            If(pbuffer.source.stb,
                pbuffer.source.ack.eq(0),
                NextState("SEND_BASE_ADDRESS")
            )
        )
        self.comb += [
            source.byte_enable.eq(pbuffer.source.be),
            If(pbuffer.source.we,
                source.wcount.eq(pbuffer.source.count)
            ).Else(
                source.rcount.eq(pbuffer.source.count)
            )
        ]

        fsm.act("SEND_BASE_ADDRESS",
            source.stb.eq(pbuffer.source.stb),
            source.eop.eq(0),
            source.data.eq(pbuffer.source.base_addr),
            If(source.ack,
                NextState("SEND_DATA")
            )
        )
        fsm.act("SEND_DATA",
            source.stb.eq(pbuffer.source.stb),
            source.eop.eq(pbuffer.source.eop),
            source.data.eq(pbuffer.source.data),
            If(source.stb & source.ack,
                pbuffer.source.ack.eq(1),
                If(source.eop,
                    NextState("IDLE")
                )
            )
        )


class _EtherboneRecord(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint(etherbone_packet_user_description(32))
        self.source = source = stream.Endpoint(etherbone_packet_user_description(32))

        # # #

        # receive record, decode it and generate mmap stream
        self.submodules.depacketizer = depacketizer = _EtherboneRecordDepacketizer()
        self.submodules.receiver = receiver = _EtherboneRecordReceiver()
        self.comb += [
            sink.connect(depacketizer.sink),
            depacketizer.source.connect(receiver.sink)
        ]

        # receive mmap stream, encode it and send records
        self.submodules.sender = sender = _EtherboneRecordSender()
        self.submodules.packetizer = packetizer = _EtherboneRecordPacketizer()
        self.comb += [
            sender.source.connect(packetizer.sink),
            packetizer.source.connect(source),
            source.length.eq(etherbone_record_header.length +
            	             (sender.source.wcount != 0)*4 + sender.source.wcount*4 +
            	             (sender.source.rcount != 0)*4 + sender.source.rcount*4)
        ]


# etherbone wishbone

class _EtherboneWishboneMaster(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint(etherbone_mmap_description(32))
        self.source = source = stream.Endpoint(etherbone_mmap_description(32))
        self.bus = bus = wishbone.Interface()

        # # #

        data = Signal(32)
        data_update = Signal()
        self.sync += If(data_update, data.eq(bus.dat_r))

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            sink.ack.eq(1),
            If(sink.stb,
                sink.ack.eq(0),
                If(sink.we,
                    NextState("WRITE_DATA")
                ).Else(
                    NextState("READ_DATA")
                )
            )
        )
        fsm.act("WRITE_DATA",
            bus.adr.eq(sink.addr),
            bus.dat_w.eq(sink.data),
            bus.sel.eq(sink.be),
            bus.stb.eq(sink.stb),
            bus.we.eq(1),
            bus.cyc.eq(1),
            If(bus.stb & bus.ack,
                sink.ack.eq(1),
                If(sink.eop,
                    NextState("IDLE")
                )
            )
        )
        fsm.act("READ_DATA",
            bus.adr.eq(sink.addr),
            bus.sel.eq(sink.be),
            bus.stb.eq(sink.stb),
            bus.cyc.eq(1),
            If(bus.stb & bus.ack,
                data_update.eq(1),
                NextState("SEND_DATA")
            )
        )
        fsm.act("SEND_DATA",
            source.stb.eq(sink.stb),
            source.eop.eq(sink.eop),
            source.base_addr.eq(sink.base_addr),
            source.addr.eq(sink.addr),
            source.count.eq(sink.count),
            source.be.eq(sink.be),
            source.we.eq(1),
            source.data.eq(data),
            If(source.stb & source.ack,
                sink.ack.eq(1),
                If(source.eop,
                    NextState("IDLE")
                ).Else(
                    NextState("READ_DATA")
                )
            )
        )


class _EtherboneWishboneSlave(Module):
    def __init__(self):
        self.bus = bus = wishbone.Interface()
        self.ready = Signal(reset=1)
        self.sink = sink = stream.Endpoint(etherbone_mmap_description(32))
        self.source = source = stream.Endpoint(etherbone_mmap_description(32))

        # # #

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            sink.ack.eq(1),
            If(bus.stb & bus.cyc,
                If(self.ready,
                    If(bus.we,
                        NextState("SEND_WRITE")
                    ).Else(
                        NextState("SEND_READ")
                    )
                ).Else(
                    NextState("SEND_ERROR")
                )
            )
        )
        fsm.act("SEND_WRITE",
            If(~self.ready,
                NextState("SEND_ERROR")
            ).Else(
                source.stb.eq(1),
                source.eop.eq(1),
                source.base_addr[2:].eq(bus.adr),
                source.count.eq(1),
                source.be.eq(bus.sel),
                source.we.eq(1),
                source.data.eq(bus.dat_w),
                If(source.stb & source.ack,
                    bus.ack.eq(1),
                    NextState("IDLE")
                )
            )
        )
        fsm.act("SEND_READ",
            If(~self.ready,
                NextState("SEND_ERROR")
            ).Else(
                source.stb.eq(1),
                source.eop.eq(1),
                source.base_addr.eq(0),
                source.count.eq(1),
                source.be.eq(bus.sel),
                source.we.eq(0),
                source.data[2:].eq(bus.adr),
                If(source.stb & source.ack,
                    NextState("WAIT_READ")
                )
            )
        )
        fsm.act("WAIT_READ",
            sink.ack.eq(1),
            If(~self.ready,
                NextState("SEND_ERROR")
            ).Elif(sink.stb & sink.we,
                bus.ack.eq(1),
                bus.dat_r.eq(sink.data),
                NextState("IDLE")
            )
        )
        fsm.act("SEND_ERROR",
            bus.ack.eq(1),
            bus.err.eq(1)
        )

# etherbone

class Etherbone(Module):
    def __init__(self, mode="master"):
        self.sink = sink = stream.Endpoint(user_description(32))
        self.source = source = stream.Endpoint(user_description(32))

        # # #

        self.submodules.packet = _EtherbonePacket(source, sink)
        self.submodules.record = _EtherboneRecord()
        if mode == "master":
            self.submodules.wishbone = _EtherboneWishboneMaster()
        elif mode == "slave":
            self.submodules.wishbone = _EtherboneWishboneSlave()
        else:
            raise ValueError

        self.comb += [
            self.packet.source.connect(self.record.sink),
            self.record.source.connect(self.packet.sink),
            self.record.receiver.source.connect(self.wishbone.sink),
            self.wishbone.source.connect(self.record.sender.sink)
        ]
