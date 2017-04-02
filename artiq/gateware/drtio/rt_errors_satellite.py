"""Protocol error reporting for satellites."""

from migen import *
from migen.genlib.cdc import PulseSynchronizer
from misoc.interconnect.csr import *


class RTErrorsSatellite(Module, AutoCSR):
    def __init__(self, rt_packet, ios):
        self.protocol_error = CSR(4)
        self.rtio_error = CSR(2)

        def error_csr(csr, *sources):
            for n, source in enumerate(sources):
                pending = Signal(related=source)
                ps = PulseSynchronizer("rtio", "sys")
                self.submodules += ps
                self.comb += ps.i.eq(source)
                self.sync += [
                    If(csr.re & csr.r[n], pending.eq(0)),
                    If(ps.o, pending.eq(1))
                ]
                self.comb += csr.w[n].eq(pending)

        # The master is normally responsible for avoiding output overflows and
        # output underflows. 
        # Error reports here are only for diagnosing internal ARTIQ bugs.
        error_csr(self.protocol_error, 
                  rt_packet.unknown_packet_type,
                  rt_packet.packet_truncated,
                  ios.write_underflow,
                  ios.write_overflow)
        error_csr(self.rtio_error,
                  ios.collision,
                  ios.busy)
