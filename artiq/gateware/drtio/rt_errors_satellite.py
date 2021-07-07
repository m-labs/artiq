"""Protocol error reporting for satellites."""

from migen import *
from migen.genlib.cdc import BlindTransfer

from misoc.interconnect.csr import *


class RTErrorsSatellite(Module, AutoCSR):
    def __init__(self, rt_packet, tsc, async_errors):
        self.protocol_error = CSR(5)
        self.underflow_channel = CSRStatus(16)
        self.underflow_timestamp_event = CSRStatus(64)
        self.underflow_timestamp_counter = CSRStatus(64)
        self.buffer_space_timeout_dest = CSRStatus(8)

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
                xfer = BlindTransfer("rio", "sys", data_width=data_width)
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

        cri = rt_packet.cri

        # The master is normally responsible for avoiding output overflows
        # and output underflows. The error reports here are only for diagnosing
        # internal ARTIQ bugs.
        underflow = Signal()
        overflow = Signal()
        underflow_error_cri = Signal(16+64+64)
        underflow_error_csr = Signal(16+64+64)
        self.comb += [
            underflow.eq(cri.o_status[1]),
            overflow.eq(cri.o_status[0]),
            underflow_error_cri.eq(Cat(cri.chan_sel[:16],
                                       cri.o_timestamp,
                                       tsc.full_ts_cri)),
            Cat(self.underflow_channel.status,
                self.underflow_timestamp_event.status,
                self.underflow_timestamp_counter.status).eq(underflow_error_csr)
        ]
        error_csr(self.protocol_error,
                  (rt_packet.unknown_packet_type, False, None, None),
                  (rt_packet.packet_truncated, False, None, None),
                  (rt_packet.buffer_space_timeout, False,
                        cri.chan_sel[16:], self.buffer_space_timeout_dest.status),
                  (underflow, True, underflow_error_cri, underflow_error_csr),
                  (overflow, True, None, None)
        )

        error_csr(self.rtio_error,
                  (async_errors.sequence_error, False,
                   async_errors.sequence_error_channel, self.sequence_error_channel.status),
                  (async_errors.collision, False,
                   async_errors.collision_channel, self.collision_channel.status),
                  (async_errors.busy, False,
                   async_errors.busy_channel, self.busy_channel.status)
        )
