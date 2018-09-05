from migen import *

from misoc.interconnect.csr import *

from artiq.gateware.rtio.cdc import BlindTransfer


class RTController(Module, AutoCSR):
    def __init__(self, rt_packet):
        self.set_time = CSR()
        self.protocol_error = CSR(4)

        set_time_stb = Signal()
        set_time_ack = Signal()
        self.submodules += CrossDomainRequest("rtio",
            set_time_stb, set_time_ack, None,
            rt_packet.set_time_stb, rt_packet.set_time_ack, None)
        self.sync += [
            If(set_time_ack, set_time_stb.eq(0)),
            If(self.set_time.re, set_time_stb.eq(1))
        ]
        self.comb += self.set_time.w.eq(set_time_stb)

        errors = [
            (rt_packet.err_unknown_packet_type, "rtio_rx"),
            (rt_packet.err_packet_truncated, "rtio_rx"),
            (rt_packet.err_command_missed, "rtio"),
            (rt_packet.err_buffer_space_timeout, "rtio")
        ]

        for n, (err_i, err_cd) in enumerate(errors):
            xfer = BlindTransfer(err_cd, "sys")
            self.submodules += xfer

            self.comb += xfer.i.eq(err_i)

            err_pending = Signal()
            self.sync += [
                If(self.protocol_error.re & self.protocol_error.r[n], err_pending.eq(0)),
                If(xfer.o, err_pending.eq(1))
            ]
            self.comb += self.protocol_error.w[n].eq(err_pending)
