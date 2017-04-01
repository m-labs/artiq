"""Protocol error reporting for satellites."""

from migen import *
from migen.genlib.cdc import PulseSynchronizer
from misoc.interconnect.csr import *


class RTErrorsSatellite(Module, AutoCSR):
    def __init__(self, rt_packet, ios):
        self.protocol_error = CSR(4)

        # The master is normally responsible for avoiding output overflows and
        # output underflows. 
        # Error reports here are only for diagnosing internal ARTIQ bugs.

        unknown_packet_type = Signal()
        packet_truncated = Signal()
        write_overflow = Signal()
        write_underflow = Signal()
        self.comb += self.protocol_error.w.eq(
            Cat(unknown_packet_type, packet_truncated,
                write_underflow, write_overflow))

        for n, (target, source) in enumerate([
                (unknown_packet_type, rt_packet.unknown_packet_type),
                (packet_truncated, rt_packet.packet_truncated),
                (write_underflow, ios.write_underflow),
                (write_overflow, ios.write_overflow)]):
            ps = PulseSynchronizer("rtio", "sys")
            self.submodules += ps
            self.comb += ps.i.eq(source)
            self.sync += [
                If(self.protocol_error.re & self.protocol_error.r[n], target.eq(0)),
                If(ps.o, target.eq(1))
            ]

