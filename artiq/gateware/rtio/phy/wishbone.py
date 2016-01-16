from migen import *
from misoc.interconnect import wishbone

from artiq.gateware.rtio import rtlink


class RT2WB(Module):
    def __init__(self, address_width, wb=None):
        if wb is None:
            wb = wishbone.Interface()
        self.wb = wb
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(
                len(wb.dat_w),
                address_width + 1,
                suppress_nop=False),
            rtlink.IInterface(
                len(wb.dat_r),
                timestamped=False)
            )

        # # #

        active = Signal()
        self.sync.rio += [
            If(self.rtlink.o.stb,
                active.eq(1),
                wb.adr.eq(self.rtlink.o.address[:address_width]),
                wb.we.eq(~self.rtlink.o.address[address_width]),
                wb.dat_w.eq(self.rtlink.o.data),
                wb.sel.eq(2**len(wb.sel) - 1)
            ),
            If(wb.ack,
                active.eq(0)
            )
        ]
        self.comb += [
            self.rtlink.o.busy.eq(active),
            wb.cyc.eq(active),
            wb.stb.eq(active),

            self.rtlink.i.stb.eq(wb.ack & ~wb.we),
            self.rtlink.i.data.eq(wb.dat_r)
        ]
