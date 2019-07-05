from migen import *
from migen.genlib.fsm import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer, BlindTransfer

from misoc.interconnect.csr import *


class ADPLLProgrammer(Module):
    def __init__(self):
        self.i2c_divider = Signal(16)
        self.i2c_address = Signal(7)

        self.adpll = Signal(24)
        self.stb = Signal()
        self.busy = Signal()
        self.nack = Signal()

        self.scl = Signal()
        self.sda_i = Signal()
        self.sda_o = Signal()
        self.sda_oe = Signal()

        self.scl.attr.add("no_retiming")
        self.sda_o.attr.add("no_retiming")
        self.sda_oe.attr.add("no_retiming")


class Si590(Module, AutoCSR):
    def __init__(self, pads):
        self.gpio_enable = CSRStorage(reset=1)
        self.gpio_in = CSRStatus(2)
        self.gpio_out = CSRStorage(2)
        self.gpio_oe = CSRStorage(2)

        self.i2c_divider = CSRStorage(16)
        self.i2c_address = CSRStorage(7)
        self.errors = CSR(2)

        # in helper clock domain
        self.adpll = Signal(24)
        self.adpll_stb = Signal()

        # # #

        programmer = ClockDomainsRenamer("helper")(ADPLLProgrammer())
        self.submodules += programmer

        self.i2c_divider.storage.attr.add("no_retiming")
        self.i2c_address.storage.attr.add("no_retiming")
        self.specials += [
            MultiReg(self.i2c_divider.storage, programmer.i2c_divider, "helper"),
            MultiReg(self.i2c_address.storage, programmer.i2c_address, "helper")
        ]
        self.comb += [
            programmer.adpll.eq(self.adpll),
            programmer.adpll_stb.eq(self.adpll_stb)
        ]

        # SCL GPIO and mux
        ts_scl = TSTriple(1)
        self.specials += ts_scl.get_tristate(pads.scl)

        status = Signal()
        self.comb += self.gpio_in.status[0].eq(status)

        self.specials += MultiReg(ts_scl.i, status)
        self.gpio_enable.storage.attr.add("no_retiming")
        self.comb += [
            If(self.gpio_enable.storage,
                ts_scl.o.eq(self.gpio_out.storage[0]),
                ts_scl.oe.eq(self.gpio_oe.storage[0])
            ).Else(
                ts_scl.o.eq(programmer.scl),
                ts_scl.oe.eq(1)
            )
        ]

        # SDA GPIO and mux
        ts_sda = TSTriple(1)
        self.specials += ts_sda.get_tristate(pads.sda)

        status = Signal()
        self.comb += self.gpio_in.status[1].eq(status)

        self.specials += MultiReg(ts_sda.i, status)
        self.gpio_enable.storage.attr.add("no_retiming")
        self.comb += [
            If(self.gpio_enable.storage,
                ts_sda.o.eq(self.gpio_out.storage[1]),
                ts_sda.oe.eq(self.gpio_oe.storage[1])
            ).Else(
                ts_sda.o.eq(programmer.sda_o),
                ts_sda.oe.eq(programmer.sda_oe)
            )
        ]
        self.specials += MultiReg(ts_sda.i, programmer.sda_i, "helper")

        # Error reporting
        collision_cdc = BlindTransfer("helper", "sys")
        self.submodules += collision_cdc
        self.comb += collision_cdc.i.eq(programmer.stb & programmer.busy)

        nack_cdc = PulseSynchronizer("helper", "sys")
        self.submodules += nack_cdc
        self.comb += nack_cdc.i.eq(programmer.nack)

        for n, trig in enumerate([collision_cdc.o, nack_cdc.o]):
            self.sync += [
                If(self.errors.re & self.errors.r[n], self.errors.w[n].eq(0)),
                If(trig, self.errors.w[n].eq(1))
            ]
