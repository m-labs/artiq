from migen import *
from migen.genlib.fsm import *

from misoc.interconnect.csr import *


class I2CClockGen(Module):
    def __init__(self, width):
        self.load = Signal(width)
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
        self.scl = Signal(reset=1)
        self.sda_o = Signal(reset=1)
        self.sda_i = Signal()

        self.submodules.cg = CEInserter()(I2CClockGen(clock_width))
        self.start = Signal()
        self.stop = Signal()
        self.write = Signal()
        self.ack = Signal()
        self.data = Signal(8)
        self.ready = Signal()

        # # #

        bits = Signal(4)
        data = Signal(8)

        fsm = CEInserter()(FSM("IDLE"))
        self.submodules += fsm

        fsm.act("IDLE",
            self.ready.eq(1),
            If(self.start,
                NextState("START0"),
            ).Elif(self.stop,
                NextState("STOP0"),
            ).Elif(self.write,
                NextValue(bits, 8),
                NextValue(data, self.data),
                NextState("WRITE0")
            )
        )

        fsm.act("START0",
            NextValue(self.scl, 1),
            NextState("START1")
        )
        fsm.act("START1",
            NextValue(self.sda_o, 0),
            NextState("IDLE")
        )

        fsm.act("STOP0",
            NextValue(self.scl, 0),
            NextState("STOP1")
        )
        fsm.act("STOP1",
            NextValue(self.sda_o, 0),
            NextState("STOP2")
        )
        fsm.act("STOP2",
            NextValue(self.scl, 1), 
            NextState("STOP3")
        )
        fsm.act("STOP3",
            NextValue(self.sda_o, 1),
            NextState("IDLE")
        )

        fsm.act("WRITE0",
            NextValue(self.scl, 0),
            NextState("WRITE1")
        )
        fsm.act("WRITE1",
            If(bits == 0,
                NextValue(self.sda_o, 1),
                NextState("READACK0"),
            ).Else(
                NextValue(self.sda_o, data[7]),
                NextState("WRITE2"),
            )
        )
        fsm.act("WRITE2",
            NextValue(self.scl, 1),
            NextValue(data[1:], data[:-1]),
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

        run = Signal()
        idle = Signal()
        self.comb += [
            run.eq((self.start | self.stop | self.write) & self.ready),
            idle.eq(~run & fsm.ongoing("IDLE")),
            self.cg.ce.eq(~idle),
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

        # # #

        master = I2CMasterMachine(16)
        self.submodules += master

        self.comb += [
            master.cg.load.eq(self.i2c_divider),
            self.scl.eq(master.scl),
            master.sda_i.eq(self.sda_i),
            self.sda_o.eq(master.sda_o)
        ]

        fsm = FSM()
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.stb,
                NextValue(self.nack, 0),
                NextState("START")
            )
        )
        fsm.act("START",
            master.start.eq(1),
            If(master.ready, NextState("DEVADDRESS"))
        )
        fsm.act("DEVADDRESS",
            master.data.eq(self.i2c_address << 1),
            master.write.eq(1),
            If(master.ready, NextState("REGADRESS"))
        )
        fsm.act("REGADRESS",
            master.data.eq(231),
            master.write.eq(1),
            If(master.ready,
                If(master.ack,
                    NextState("DATA0")
                ).Else(
                    NextValue(self.nack, 1),
                    NextState("STOP")
                )
            )
        )
        fsm.act("DATA0",
            master.data.eq(self.adpll[0:8]),
            master.write.eq(1),
            If(master.ready,
                If(master.ack,
                    NextState("DATA1")
                ).Else(
                    NextValue(self.nack, 1),
                    NextState("STOP")
                )
            )
        )
        fsm.act("DATA1",
            master.data.eq(self.adpll[8:16]),
            master.write.eq(1),
            If(master.ready,
                If(master.ack,
                    NextState("DATA2")
                ).Else(
                    NextValue(self.nack, 1),
                    NextState("STOP")
                )
            )
        )
        fsm.act("DATA2",
            master.data.eq(self.adpll[16:24]),
            master.write.eq(1),
            If(master.ready,
                If(~master.ack, NextValue(self.nack, 1)),
                NextState("STOP")
            )
        )
        fsm.act("STOP",
            master.stop.eq(1),
            If(master.ready,
                If(~master.ack, NextValue(self.nack, 1)),
                NextState("IDLE")
            )
        )

        self.comb += self.busy.eq(~fsm.ongoing("IDLE"))


class Si549(Module, AutoCSR):
    def __init__(self, pads):
        self.i2c_divider = CSRStorage(16, reset=75)
        self.i2c_address = CSRStorage(7)

        self.adpll = CSRStorage(24)
        self.adpll_stb = CSR()
        self.adpll_busy = CSRStatus()
        self.nack = CSRStatus()

        self.bitbang_enable = CSRStorage()

        self.sda_oe = CSRStorage()
        self.sda_out = CSRStorage()
        self.sda_in = CSRStatus()
        self.scl_oe = CSRStorage()
        self.scl_out = CSRStorage()

        # # #

        self.submodules.programmer = ADPLLProgrammer()

        self.sync += self.programmer.stb.eq(self.adpll_stb.re)

        self.comb += [
            self.programmer.i2c_divider.eq(self.i2c_divider.storage),
            self.programmer.i2c_address.eq(self.i2c_address.storage),
            self.programmer.adpll.eq(self.adpll.storage),
            self.adpll_busy.status.eq(self.programmer.busy),
            self.nack.status.eq(self.programmer.nack)
        ]

        # I2C with bitbang/gateware mode select
        sda_t = TSTriple(1)
        scl_t = TSTriple(1)
        self.specials += [
            sda_t.get_tristate(pads.sda),
            scl_t.get_tristate(pads.scl)
        ]

        self.comb += [
            If(self.bitbang_enable.storage,
                sda_t.oe.eq(self.sda_oe.storage),
                sda_t.o.eq(self.sda_out.storage),
                self.sda_in.status.eq(sda_t.i),
                scl_t.oe.eq(self.scl_oe.storage),
                scl_t.o.eq(self.scl_out.storage)
            ).Else(
                sda_t.oe.eq(~self.programmer.sda_o),
                sda_t.o.eq(0),
                self.programmer.sda_i.eq(sda_t.i),
                scl_t.oe.eq(~self.programmer.scl),
                scl_t.o.eq(0),
            )
        ]