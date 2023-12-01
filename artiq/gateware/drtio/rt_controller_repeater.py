from migen import *
from migen.genlib.cdc import MultiReg, BlindTransfer

from misoc.interconnect.csr import *

from artiq.gateware.drtio.cdc import CrossDomainRequest


class RTController(Module, AutoCSR):
    def __init__(self, rt_packet):
        self.reset = CSRStorage()
        self.set_time = CSR()
        self.protocol_error = CSR(4)
        self.command_missed_cmd = CSRStatus(2)
        self.command_missed_chan_sel = CSRStatus(24)
        self.buffer_space_timeout_dest = CSRStatus(8)

        self.sync += rt_packet.reset.eq(self.reset.storage)

        self.sync += [
            If(rt_packet.set_time_ack, rt_packet.set_time_stb.eq(0)),
            If(self.set_time.re, rt_packet.set_time_stb.eq(1))
        ]
        self.comb += self.set_time.w.eq(rt_packet.set_time_stb)

        errors = [
            (rt_packet.err_unknown_packet_type, "rtio_rx", None, None),
            (rt_packet.err_packet_truncated, "rtio_rx", None, None),
            (rt_packet.err_command_missed, "sys",
                Cat(rt_packet.command_missed_cmd, rt_packet.command_missed_chan_sel),
                Cat(self.command_missed_cmd.status, self.command_missed_chan_sel.status)),
            (rt_packet.err_buffer_space_timeout, "sys",
                rt_packet.buffer_space_destination, self.buffer_space_timeout_dest.status)
        ]

        for n, (err_i, err_cd, din, dout) in enumerate(errors):
            if din is not None:
                data_width = len(din)
            else:
                data_width = 0

            xfer = BlindTransfer(err_cd, "sys", data_width=data_width)
            self.submodules += xfer

            self.comb += xfer.i.eq(err_i)

            err_pending = Signal()
            self.sync += [
                If(self.protocol_error.re & self.protocol_error.r[n], err_pending.eq(0)),
                If(xfer.o, err_pending.eq(1))
            ]
            self.comb += self.protocol_error.w[n].eq(err_pending)

            if din is not None:
                self.comb += xfer.data_i.eq(din)
                self.sync += If(xfer.o & ~err_pending, dout.eq(xfer.data_o))
