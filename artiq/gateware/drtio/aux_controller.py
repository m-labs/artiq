"""Auxiliary controller, common to satellite and master"""

from migen import *
from migen.fhdl.simplify import FullMemoryWE
from migen.genlib.cdc import MultiReg, PulseSynchronizer

from misoc.interconnect.csr import *
from misoc.interconnect import stream 
from misoc.interconnect import wishbone


max_packet = 1024
aux_buffer_count = 8


class Transmitter(Module, AutoCSR):
    def __init__(self, link_layer, min_mem_dw):
        ll_dw = len(link_layer.tx_aux_data)
        mem_dw = max(min_mem_dw, ll_dw)

        self.aux_tx_length = CSRStorage(bits_for(max_packet),
                                        alignment_bits=log2_int(mem_dw//8))
        self.aux_tx = CSR()
        self.specials.mem = Memory(mem_dw, max_packet//(mem_dw//8))

        converter = stream.Converter(mem_dw, ll_dw)
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
        self.sync += [
            If(link_layer.tx_aux_ack,
                frame_r.eq(link_layer.tx_aux_frame),
                If(frame_r & ~link_layer.tx_aux_frame, seen_eop.eq(1))
            ),
            If(seen_eop_rst, seen_eop.eq(0))
        ]

        mem_port = self.mem.get_port()
        self.specials += mem_port

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

        tx_done = Signal()
        self.sync += [
            frame_counter.eq(frame_counter_next),
            If(self.aux_tx.re, self.aux_tx.w.eq(1)),
            If(tx_done, self.aux_tx.w.eq(0))
        ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            frame_counter_rst.eq(1),
            seen_eop_rst.eq(1),
            If(self.aux_tx.re, NextState("TRANSMIT"))
        )
        fsm.act("TRANSMIT",
            converter.sink.stb.eq(1),
            If(converter.sink.ack,
                frame_counter_ce.eq(1)
            ),
            If(frame_counter_next == self.aux_tx_length.storage,
                NextState("WAIT_INTERFRAME"))
        )
        fsm.act("WAIT_INTERFRAME",
            If(seen_eop,
                tx_done.eq(1),
                NextState("IDLE")
            )
        )


class Receiver(Module, AutoCSR):
    def __init__(self, link_layer, min_mem_dw):
        self.aux_rx_present = CSR()
        self.aux_rx_error = CSR()
        self.aux_read_pointer = CSR(log2_int(aux_buffer_count))

        ll_dw = len(link_layer.rx_aux_data)
        mem_dw = max(min_mem_dw, ll_dw)
        self.specials.mem = Memory(mem_dw, aux_buffer_count*max_packet//(mem_dw//8))

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

        # write pointer represents where the gateware is
        write_pointer = Signal(log2_int(aux_buffer_count))
        write_pointer_sys = Signal.like(write_pointer)
        # read pointer represents where CPU is
        # write reaching read is an error, read reaching write is buffer clear
        read_pointer = Signal.like(write_pointer)
        read_pointer_rx = Signal.like(write_pointer)

        read_pointer.attr.add("no_retiming")
        write_pointer.attr.add("no_retiming")
        signal_error = PulseSynchronizer("rtio_rx", "sys")

        self.specials += [
            MultiReg(read_pointer, read_pointer_rx, "rtio_rx"),
            MultiReg(write_pointer, write_pointer_sys)
        ]

        frame_counter_nbits = bits_for(max_packet) - log2_int(mem_dw//8)
        frame_counter = Signal(frame_counter_nbits)
        # frame counter requires one more bit to represent overflow (bits_for)
        # actual valid packet will be addressed with one bit less
        packet_nbits = frame_counter_nbits - 1
        self.comb += [
            mem_port.adr[:packet_nbits].eq(frame_counter),
            # bits above the frame counter point to current frame
            mem_port.adr[packet_nbits:].eq(write_pointer),
            mem_port.dat_w.eq(converter.source.data),
            converter.source.ack.eq(1),
            self.aux_read_pointer.w.eq(read_pointer)
        ]

        self.submodules += signal_error
        self.sync += [
            If(self.aux_rx_error.re, self.aux_rx_error.w.eq(0)),
            If(signal_error.o, self.aux_rx_error.w.eq(1)),
            self.aux_rx_present.w.eq(~(read_pointer == write_pointer_sys)),
            If(self.aux_rx_present.re & self.aux_rx_present.w,
                read_pointer.eq(read_pointer + 1)),
        ]

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
                NextValue(frame_counter, 0),
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
            NextState("IDLE"),
            If((write_pointer + 1) == read_pointer_rx,
                # on full buffer, overwrite only current frame
                signal_error.i.eq(1)
            ).Else(
                NextValue(write_pointer, write_pointer + 1)
            ),
            If(converter.source.stb, signal_error.i.eq(1))
        )


# TODO: FullMemoryWE should be applied by migen.build
@FullMemoryWE()
class DRTIOAuxController(Module):
    def __init__(self, link_layer, dw=32):
        wsb = log2_int(dw//8)

        self.bus = wishbone.Interface(data_width=dw, adr_width=32-wsb)
        self.submodules.transmitter = Transmitter(link_layer, len(self.bus.dat_w))
        self.submodules.receiver = Receiver(link_layer, len(self.bus.dat_w))

        tx_sdram_if = wishbone.SRAM(self.transmitter.mem, read_only=False, data_width=dw)
        rx_sdram_if = wishbone.SRAM(self.receiver.mem, read_only=True, data_width=dw)
        decoder = wishbone.Decoder(self.bus,
            [(lambda a: a[log2_int(max_packet*aux_buffer_count)-wsb] == 0, tx_sdram_if.bus),
             (lambda a: a[log2_int(max_packet*aux_buffer_count)-wsb] == 1, rx_sdram_if.bus)],
            register=True)
        self.submodules += tx_sdram_if, rx_sdram_if, decoder

    def get_csrs(self):
        return self.transmitter.get_csrs() + self.receiver.get_csrs()
