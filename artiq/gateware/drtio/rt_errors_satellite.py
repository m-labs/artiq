"""Protocol error reporting for satellites."""

from migen import *
from misoc.interconnect.csr import *

from artiq.gateware.rtio.cdc import BlindTransfer


class RTErrorsSatellite(Module, AutoCSR):
    def __init__(self, rt_packet, outputs):
        self.protocol_error = CSR(4)
        self.rtio_error = CSR(3)
        self.sequence_error_channel = CSRStatus(16)
        self.collision_channel = CSRStatus(16)
        self.busy_channel = CSRStatus(16)

        def error_csr(csr, *sources):
            for n, (source, detect_edges, din, dout) in enumerate(sources):
                assert isinstance(source, Signal)

                if din is not None:
                    data_width = len(din)
                else:
                    data_width = 0
                xfer = BlindTransfer(odomain="sys", data_width=data_width)
                self.submodules += xfer

                if detect_edges:
                    source_r = Signal()
                    self.sync.rio += source_r.eq(source)
                    self.comb += xfer.i.eq(source & ~source_r)
                else:
                    self.comb += xfer.i.eq(source)

                pending = Signal(related=source)
                self.sync += [
                    If(csr.re & csr.r[n], pending.eq(0)),
                    If(xfer.o, pending.eq(1))
                ]
                self.comb += csr.w[n].eq(pending)

                if din is not None:
                    self.comb += xfer.data_i.eq(din)
                    self.sync += If(xfer.o & ~pending, dout.eq(xfer.data_o))


        # The master is normally responsible for avoiding output overflows
        # and output underflows. The error reports here are only for diagnosing
        # internal ARTIQ bugs.
        underflow = Signal()
        overflow = Signal()
        self.comb += [
            underflow.eq(outputs.cri.o_status[1]),
            overflow.eq(outputs.cri.o_status[0])
        ]
        error_csr(self.protocol_error,
                  (rt_packet.unknown_packet_type, False, None, None),
                  (rt_packet.packet_truncated, False, None, None),
                  (underflow, True, None, None),
                  (overflow, True, None, None)
        )
        error_csr(self.rtio_error,
                  (outputs.sequence_error, False,
                   outputs.sequence_error_channel, self.sequence_error_channel.status),
                  (outputs.collision, False,
                   outputs.collision_channel, self.collision_channel.status),
                  (outputs.busy, False,
                   outputs.busy_channel, self.busy_channel.status)
        )
