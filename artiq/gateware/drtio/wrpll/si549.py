from migen import *
from migen.genlib.fsm import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer, BlindTransfer

from misoc.interconnect.csr import *


class I2CClockGen(Module):
    def __init__(self, width):
        self.load  = Signal(width)
        self.clk2x = Signal()

        cnt = Signal.like(self.load)
        self.comb += [
            self.clk2x.eq(cnt == 0),
        ]
        self.sync += [
            If(self.clk2x,
                cnt.eq(self.load),
            ).Else(
                cnt.eq(cnt - 1),
            )
        ]


class I2CMasterMachine(Module):
    def __init__(self, clock_width):
        self.scl   = Signal(reset=1)
        self.sda_o = Signal(reset=1)
        self.sda_i = Signal()

        self.submodules.cg  = CEInserter()(I2CClockGen(clock_width))
        self.idle  = Signal()
        self.start = Signal()
        self.stop  = Signal()
        self.write = Signal()
        self.read  = Signal()
        self.ack   = Signal()
        self.data  = Signal(8)

        ###

        busy = Signal()
        bits = Signal(4)

        fsm = CEInserter()(FSM("IDLE"))
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.start,
                NextState("START0"),
            ).Elif(self.stop & self.start,
                NextState("RESTART0"),
            ).Elif(self.stop,
                NextState("STOP0"),
            ).Elif(self.write,
                NextValue(bits, 8),
                NextState("WRITE0"),
            ).Elif(self.read,
                NextValue(bits, 8),
                NextState("READ0"),
            )
        )

        fsm.act("START0",
            NextValue(self.scl, 1),
            NextState("START1"))
        fsm.act("START1",
            NextValue(self.sda_o, 0),
            NextState("IDLE"))

        fsm.act("RESTART0",
            NextValue(self.scl, 0),
            NextState("RESTART1"))
        fsm.act("RESTART1",
            NextValue(self.sda_o, 1),
            NextState("START0"))

        fsm.act("STOP0",
            NextValue(self.scl, 0),
            NextState("STOP1"))
        fsm.act("STOP1",
            NextValue(self.scl, 1),
            NextValue(self.sda_o, 0),
            NextState("STOP2"))
        fsm.act("STOP2",
            NextValue(self.sda_o, 1),
            NextState("IDLE"))

        fsm.act("WRITE0",
            NextValue(self.scl, 0),
            If(bits == 0,
                NextValue(self.sda_o, 1),
                NextState("READACK0"),
            ).Else(
                NextValue(self.sda_o, self.data[7]),
                NextState("WRITE1"),
            )
        )
        fsm.act("WRITE1",
            NextValue(self.scl, 1),
            NextValue(self.data[1:], self.data[:-1]),
            NextValue(bits, bits - 1),
            NextState("WRITE0"),
        )
        fsm.act("READACK0",
            NextValue(self.scl, 1),
            NextState("READACK1"),
        )
        fsm.act("READACK1",
            NextValue(self.ack, ~self.sda_i),
            NextState("IDLE")
        )

        fsm.act("READ0",
            NextValue(self.scl, 0),
            NextState("READ1"),
        )
        fsm.act("READ1",
            NextValue(self.data[0], self.sda_i),
            NextValue(self.scl, 0),
            If(bits == 0,
                NextValue(self.sda_o, ~self.ack),
                NextState("WRITEACK0"),
            ).Else(
                NextValue(self.sda_o, 1),
                NextState("READ2"),
            )
        )
        fsm.act("READ2",
            NextValue(self.scl, 1),
            NextValue(self.data[:-1], self.data[1:]),
            NextValue(bits, bits - 1),
            NextState("READ1"),
        )
        fsm.act("WRITEACK0",
            NextValue(self.scl, 1),
            NextState("IDLE"),
        )

        run = Signal()
        self.comb += [
            run.eq(self.start | self.stop | self.write | self.read),
            self.idle.eq(~run & fsm.ongoing("IDLE")),
            self.cg.ce.eq(~self.idle),
            fsm.ce.eq(run | self.cg.clk2x),
        ]


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

        self.scl.attr.add("no_retiming")
        self.sda_o.attr.add("no_retiming")

        # # #

        master = I2CMasterMachine(16)
        self.submodules += master

        self.comb += [
            master.cg.load.eq(self.i2c_divider.storage),
            self.scl.eq(master.scl),
            master.sda_i.eq(self.sda_i),
            self.sda_o.eq(master.sda_o)
        ]


class Si549(Module, AutoCSR):
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

        self.gpio_enable.storage.attr.add("no_retiming")
        self.gpio_out.storage.attr.add("no_retiming")
        self.gpio_oe.storage.attr.add("no_retiming")

        # SCL GPIO and mux
        ts_scl = TSTriple(1)
        self.specials += ts_scl.get_tristate(pads.scl)

        status = Signal()
        self.comb += self.gpio_in.status[0].eq(status)

        self.specials += MultiReg(ts_scl.i, status)
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
        self.comb += [
            If(self.gpio_enable.storage,
                ts_sda.o.eq(self.gpio_out.storage[1]),
                ts_sda.oe.eq(self.gpio_oe.storage[1])
            ).Else(
                ts_sda.o.eq(0),
                ts_sda.oe.eq(~programmer.sda_o)
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
