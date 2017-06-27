"""Protocol error reporting for satellites."""

from migen import *
from misoc.interconnect.csr import *

from artiq.gateware.rtio.cdc import BlindTransfer


class RTErrorsSatellite(Module, AutoCSR):
    def __init__(self, rt_packet, ios):
        self.protocol_error = CSR(5)
        self.rtio_error = CSR(2)

        def error_csr(csr, *sources):
            for n, source in enumerate(sources):
                pending = Signal(related=source)
                xfer = BlindTransfer(odomain="sys")
                self.submodules += xfer
                self.comb += xfer.i.eq(source)
                self.sync += [
                    If(csr.re & csr.r[n], pending.eq(0)),
                    If(xfer.o, pending.eq(1))
                ]
                self.comb += csr.w[n].eq(pending)

        # The master is normally responsible for avoiding output overflows,
        # output underflows, and sequence errors.
        # Error reports here are only for diagnosing internal ARTIQ bugs.
        error_csr(self.protocol_error, 
                  rt_packet.unknown_packet_type,
                  rt_packet.packet_truncated,
                  ios.write_underflow,
                  ios.write_overflow,
                  ios.write_sequence_error)
        error_csr(self.rtio_error,
                  ios.collision,
                  ios.busy)
