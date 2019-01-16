"""Auxiliary controller, common to satellite and master"""

from migen import *
from migen.fhdl.simplify import FullMemoryWE
from migen.genlib.cdc import MultiReg, PulseSynchronizer

from misoc.interconnect.csr import *
from misoc.interconnect import stream 
from misoc.interconnect import wishbone


max_packet = 1024


class Transmitter(Module, AutoCSR):
    def __init__(self, link_layer, min_mem_dw):
        ll_dw = len(link_layer.tx_aux_data)
        mem_dw = max(min_mem_dw, ll_dw)

        self.aux_tx_length = CSRStorage(bits_for(max_packet),
                                        alignment_bits=log2_int(mem_dw//8))
        self.aux_tx = CSR()
        self.specials.mem = Memory(mem_dw, max_packet//(mem_dw//8))

        converter = ClockDomainsRenamer("rtio")(
            stream.Converter(mem_dw, ll_dw))
        self.submodules += converter

        # when continuously fed, the Converter outputs data continuously
        self.comb += [
            converter.source.ack.eq(link_layer.tx_aux_ack),
            link_layer.tx_aux_frame.eq(converter.source.stb),
            link_layer.tx_aux_data.eq(converter.source.data)
        ]

        seen_eop_rst = Signal()
        frame_r = Signal()
        seen_eop = Signal()
        self.sync.rtio += [
            If(link_layer.tx_aux_ack,
                frame_r.eq(link_layer.tx_aux_frame),
                If(frame_r & ~link_layer.tx_aux_frame, seen_eop.eq(1))
            ),
            If(seen_eop_rst, seen_eop.eq(0))
        ]

        mem_port = self.mem.get_port(clock_domain="rtio")
        self.specials += mem_port

        self.aux_tx_length.storage.attr.add("no_retiming")
        tx_length = Signal(bits_for(max_packet))
        self.specials += MultiReg(self.aux_tx_length.storage, tx_length, "rtio")

        frame_counter_nbits = bits_for(max_packet) - log2_int(mem_dw//8)
        frame_counter = Signal(frame_counter_nbits)
        frame_counter_next = Signal(frame_counter_nbits)
        frame_counter_ce = Signal()
        frame_counter_rst = Signal()
        self.comb += [
            frame_counter_next.eq(frame_counter),
            If(frame_counter_rst,
                frame_counter_next.eq(0)
            ).Elif(frame_counter_ce,
                frame_counter_next.eq(frame_counter + 1)
            ),
            mem_port.adr.eq(frame_counter_next),
            converter.sink.data.eq(mem_port.dat_r)
        ]
        self.sync.rtio += frame_counter.eq(frame_counter_next)

        start_tx = PulseSynchronizer("sys", "rtio")
        tx_done = PulseSynchronizer("rtio", "sys")
        self.submodules += start_tx, tx_done
        self.comb += start_tx.i.eq(self.aux_tx.re)
        self.sync += [
            If(tx_done.o, self.aux_tx.w.eq(0)),
            If(self.aux_tx.re, self.aux_tx.w.eq(1))
        ]

        fsm = ClockDomainsRenamer("rtio")(FSM(reset_state="IDLE"))
        self.submodules += fsm

        fsm.act("IDLE",
            frame_counter_rst.eq(1),
            seen_eop_rst.eq(1),
            If(start_tx.o, NextState("TRANSMIT"))
        )
        fsm.act("TRANSMIT",
            converter.sink.stb.eq(1),
            If(converter.sink.ack,
                frame_counter_ce.eq(1)
            ),
            If(frame_counter_next == tx_length, NextState("WAIT_INTERFRAME"))
        )
        fsm.act("WAIT_INTERFRAME",
            If(seen_eop,
                tx_done.i.eq(1),
                NextState("IDLE")
            )
        )


class Receiver(Module, AutoCSR):
    def __init__(self, link_layer, min_mem_dw):
        self.aux_rx_length = CSRStatus(bits_for(max_packet))
        self.aux_rx_present = CSR()
        self.aux_rx_error = CSR()

        ll_dw = len(link_layer.rx_aux_data)
        mem_dw = max(min_mem_dw, ll_dw)
        self.specials.mem = Memory(mem_dw, max_packet//(mem_dw//8))

        converter = ClockDomainsRenamer("rtio_rx")(
            stream.Converter(ll_dw, mem_dw))
        self.submodules += converter

        # when continuously drained, the Converter accepts data continuously
        frame_r = Signal()
        self.sync.rtio_rx += [
            If(link_layer.rx_aux_stb,
                frame_r.eq(link_layer.rx_aux_frame),
                converter.sink.data.eq(link_layer.rx_aux_data)
            )
        ]
        self.comb += [
            converter.sink.stb.eq(link_layer.rx_aux_stb & frame_r),
            converter.sink.eop.eq(converter.sink.stb & ~link_layer.rx_aux_frame)
        ]

        mem_port = self.mem.get_port(write_capable=True, clock_domain="rtio_rx")
        self.specials += mem_port

        frame_counter_nbits = bits_for(max_packet) - log2_int(mem_dw//8)
        frame_counter = Signal(frame_counter_nbits)
        self.comb += [
            mem_port.adr.eq(frame_counter),
            mem_port.dat_w.eq(converter.source.data),
            converter.source.ack.eq(1)
        ]

        frame_counter.attr.add("no_retiming")
        frame_counter_sys = Signal(frame_counter_nbits)
        self.specials += MultiReg(frame_counter, frame_counter_sys)
        self.comb += self.aux_rx_length.status.eq(frame_counter_sys << log2_int(mem_dw//8))

        signal_frame = PulseSynchronizer("rtio_rx", "sys")
        frame_ack = PulseSynchronizer("sys", "rtio_rx")
        signal_error = PulseSynchronizer("rtio_rx", "sys")
        self.submodules += signal_frame, frame_ack, signal_error
        self.sync += [
            If(self.aux_rx_present.re, self.aux_rx_present.w.eq(0)),
            If(signal_frame.o, self.aux_rx_present.w.eq(1)),
            If(self.aux_rx_error.re, self.aux_rx_error.w.eq(0)),
            If(signal_error.o, self.aux_rx_error.w.eq(1))
        ]
        self.comb += frame_ack.i.eq(self.aux_rx_present.re)

        fsm = ClockDomainsRenamer("rtio_rx")(FSM(reset_state="IDLE"))
        self.submodules += fsm

        sop = Signal(reset=1)
        self.sync.rtio_rx += \
            If(converter.source.stb,
                If(converter.source.eop,
                    sop.eq(1)
                ).Else(
                    sop.eq(0)
                )
            )

        fsm.act("IDLE",
            If(converter.source.stb & sop,
                NextValue(frame_counter, frame_counter + 1),
                mem_port.we.eq(1),
                If(converter.source.eop,
                    NextState("SIGNAL_FRAME")
                ).Else(
                    NextState("FRAME")
                )
            ).Else(
                NextValue(frame_counter, 0)
            )
        )
        fsm.act("FRAME",
            If(converter.source.stb,
                NextValue(frame_counter, frame_counter + 1),
                mem_port.we.eq(1),
                If(frame_counter == max_packet,
                    mem_port.we.eq(0),
                    signal_error.i.eq(1),
                    NextState("IDLE")  # discard the rest of the frame
                ),
                If(converter.source.eop,
                    NextState("SIGNAL_FRAME")
                )
            )
        )
        fsm.act("SIGNAL_FRAME",
            signal_frame.i.eq(1),
            NextState("WAIT_ACK"),
            If(converter.source.stb, signal_error.i.eq(1))
        )
        fsm.act("WAIT_ACK",
            If(frame_ack.o,
                NextValue(frame_counter, 0), 
                NextState("IDLE")
            ),
            If(converter.source.stb, signal_error.i.eq(1))
        )


# TODO: FullMemoryWE should be applied by migen.build
@FullMemoryWE()
class DRTIOAuxController(Module):
    def __init__(self, link_layer):
        self.bus = wishbone.Interface()
        self.submodules.transmitter = Transmitter(link_layer, len(self.bus.dat_w))
        self.submodules.receiver = Receiver(link_layer, len(self.bus.dat_w))

        tx_sdram_if = wishbone.SRAM(self.transmitter.mem, read_only=False)
        rx_sdram_if = wishbone.SRAM(self.receiver.mem, read_only=True)
        wsb = log2_int(len(self.bus.dat_w)//8)
        decoder = wishbone.Decoder(self.bus,
            [(lambda a: a[log2_int(max_packet)-wsb] == 0, tx_sdram_if.bus),
             (lambda a: a[log2_int(max_packet)-wsb] == 1, rx_sdram_if.bus)],
            register=True)
        self.submodules += tx_sdram_if, rx_sdram_if, decoder

    def get_csrs(self):
        return self.transmitter.get_csrs() + self.receiver.get_csrs()
