"""Protocol error reporting for satellites."""

from migen import *
from misoc.interconnect.csr import *

from artiq.gateware.rtio.cdc import BlindTransfer


class RTErrorsSatellite(Module, AutoCSR):
    def __init__(self, rt_packet, outputs):
        self.protocol_error = CSR(4)
        self.rtio_error = CSR(3)

        def error_csr(csr, *sources):
            for n, (source, detect_edges) in enumerate(sources):
                assert isinstance(source, Signal)
                pending = Signal(related=source)
                xfer = BlindTransfer(odomain="sys")
                self.submodules += xfer
                if detect_edges:
                    source_r = Signal()
                    self.sync.rio += source_r.eq(source)
                    self.comb += xfer.i.eq(source & source_r)
                else:
                    self.comb += xfer.i.eq(source)
                self.sync += [
                    If(csr.re & csr.r[n], pending.eq(0)),
                    If(xfer.o, pending.eq(1))
                ]
                self.comb += csr.w[n].eq(pending)


        # The master is normally responsible for avoiding output overflows
        # and output underflows. The error reports here are only for diagnosing
        # internal ARTIQ bugs.
        underflow = Signal()
        overflow = Signal()
        sequence_error = Signal()
        self.comb += [
            underflow.eq(outputs.cri.o_status[1]),
            overflow.eq(outputs.cri.o_status[0]),
            sequence_error.eq(outputs.cri.o_status[2])
        ]
        error_csr(self.protocol_error,
                  (rt_packet.unknown_packet_type, False),
                  (rt_packet.packet_truncated, False),
                  (underflow, True),
                  (overflow, True)
        )
        error_csr(self.rtio_error,
                  (sequence_error, True),
                  (outputs.collision, False),
                  (outputs.busy, False)
        )
