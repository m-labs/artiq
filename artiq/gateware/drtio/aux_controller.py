from migen import *
from migen.fhdl.simplify import FullMemoryWE

from misoc.interconnect.csr import *
from misoc.interconnect import stream 
from misoc.interconnect import wishbone


max_packet = 1024

class Transmitter(Module, AutoCSR):
    def __init__(self, link_layer, min_mem_dw):
        # TODO


class Receiver(Module, AutoCSR):
    def __init__(self, link_layer, min_mem_dw):
        self.aux_rx_length = CSRStatus(bits_for(max_packet))
        self.aux_rx_present = CSR()
        self.aux_rx_error = CSR()

        ll_dw = len(link_layer.rx_aux_data)
        mem_dw = max(min_mem_dw, ll_dw)
        self.specials.mem = Memory(mem_dw, max_packet//(mem_dw//8))

        converter = stream.Converter(ll_dw, mem_dw)
        self.submodules += converter

        self.sync.rtio_rx += [
            converter.sink.stb.eq(link_layer.rx_aux_frame),
            converter.sink.data.eq(link_layer.rx_aux_data)
        ]
        self.comb += converter.sink.eop.eq(~link_layer.rx_aux_frame)

        mem_port = self.mem.get_port(write_capable=True, clock_domain="rtio_rx")
        self.specials += mem_port

        frame_counter_nbits = bits_for(max_packet) - log2_int(mem_dw//8)
        frame_counter = Signal(frame_counter_nbits)
        self.comb += [
            mem_port.adr.eq(frame_counter),
            mem_port.dat_w.eq(link_layer.rx_aux_data)
        ]

        frame_counter.attr.add("no_retiming")
        frame_counter_sys = Signal(frame_counter_nbits)
        self.specials += MultiReg(frame_counter, frame_counter_sys)
        self.comb += aux_rx_length.status.eq(frame_counter_sys << log2_int(mem_dw//8))

        signal_frame = PulseSynchronizer("rtio_rx", "sys")
        frame_ack = PulseSynchronizer("sys", "rtio_rx")
        signal_error = PulseSynchronizer("rtio_rx", "sys")
        self.submodules += signal_frame, signal_error
        self.sync += [
            If(self.aux_rx_present.re, self.aux_rx_present.w.eq(0)),
            If(signal_frame.o, self.aux_rx_present.w.eq(1)),
            If(self.aux_rx_error.re, self.aux_rx_error.w.eq(0)),
            If(signal_error.o, self.aux_rx_error.eq(1))
        ]
        self.comb += frame_ack.i.eq(self.aux_rx_present.re)

        fsm = ClockDomainsRenamer("rtio_rx")(FSM(reset_state="IDLE"))
        self.submodules += fsm

        rx_aux_frame_r = Signal()
        self.sync.rtio_rx += rx_aux_frame_r.eq(link_layer.rx_aux_frame)

        fsm.act("IDLE",
            If(link_layer.rx_aux_frame & ~rx_aux_frame_r,
                NextValue(frame_counter, frame_counter + 1),
                mem_port.we.eq(1),
                NextState("FRAME")
            ).Else(
                NextValue(frame_counter, 0)
            )
        )
        fsm.act("FRAME",
            If(link_layer.rx_aux_frame,
                NextValue(frame_counter, frame_counter + 1),
                mem_port.we.eq(1),
                If(frame_counter == max_packet,
                    mem_port.we.eq(0),
                    signal_error.i.eq(1),
                    NextState("IDLE")  # remainder of the frame discarded
                )
            ).Else(
                signal_frame.i.eq(1),
                NextState("WAIT_ACK")
            )
        )
        fsm.act("WAIT_ACK",
            If(frame_ack.o,
                NextValue(frame_counter, 0), 
                NextState("IDLE")
            ),
            If(link_layer.rx_aux_frame, signal_error.i.eq(1))
        )


class AuxController(Module):
    def __init__(self, link_layer):
        self.bus = wishbone.Interface()
        self.submodules.transmitter = Transmitter(link_layer, len(self.bus.dat_w))
        self.submodules.receiver = Receiver(link_layer, len(self.bus.dat_w))

        # TODO: FullMemoryWE should be applied by migen.build
        tx_sdram_if = FullMemoryWE()(self.transmitter.mem, read_only=False)
        rx_sdram_if = wishbone.SRAM(self.receiver.mem, read_only=True)
        wsb = log2_int(len(self.bus.dat_w)//8)
        decoder = wishbone.Decoder(self.bus,
            [(lambda a: a[log2_int(max_packet)-wsb] == 0, tx_sdram_if)
             (lambda a: a[log2_int(max_packet)-wsb] == 1, rx_sdram_if)],
            register=True)
        self.submodules += tx_sdram_if, rx_sdram_if, decoder

    def get_csrs(self):
        return self.transmitter.get_csrs() + self.receiver.get_csrs()
