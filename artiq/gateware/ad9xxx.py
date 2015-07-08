from migen.fhdl.std import *
from migen.genlib.fsm import *
from migen.genlib.misc import WaitTimer
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation


class AD9xxx(Module):
    """Wishbone interface to the AD9858 and AD9914 DDS chips.

    Addresses 0-2**flen(pads.a)-1 map the AD9xxx registers.

    Write to address 2**flen(pads.a) to pulse the FUD signal.
    Address 2**flen(pads.a)+1 is a GPIO register that controls the
    sel and reset signals. rst is mapped to bit 0, followed by sel.

    Write timing:
    Address is set one cycle before assertion of we_n.
    we_n is asserted for one cycle, at the same time as valid data is driven.

    Read timing:
    Address is set one cycle before assertion of rd_n.
    rd_n is asserted for read_wait_cycles, data is sampled at the end.
    rd_n is deasserted and data bus is not driven again before hiz_wait_cycles.

    Design:
    All IO pads are registered.

    With QC1 adapter:
    LVDS driver/receiver propagation delays are 3.6+4.5 ns max
    LVDS state transition delays are 20, 15 ns max
    Schmitt trigger delays are 6.4ns max
    Round-trip addr A setup (> RX, RD, D to Z), RD prop, D valid (< D
    valid), D prop is ~15 + 10 + 20 + 10 = 55ns
    """
    def __init__(self, pads,
                 read_wait_cycles=10, hiz_wait_cycles=3,
                 bus=None):
        if bus is None:
            bus = wishbone.Interface(data_width=flen(pads.d))
        self.bus = bus

        # # #

        dts = TSTriple(flen(pads.d))
        self.specials += dts.get_tristate(pads.d)
        hold_address = Signal()
        dr = Signal(flen(pads.d))
        rx = Signal()
        self.sync += [
            If(~hold_address, pads.a.eq(bus.adr)),
            dts.o.eq(bus.dat_w),
            dr.eq(dts.i),
            dts.oe.eq(~rx)
        ]

        gpio = Signal(flen(pads.sel) + 1)
        gpio_load = Signal()
        self.sync += If(gpio_load, gpio.eq(bus.dat_w))
        if hasattr(pads, "rst"):
            self.comb += pads.rst.eq(gpio[0])
        else:
            self.comb += pads.rst_n.eq(~gpio[0])
        self.comb += pads.sel.eq(gpio[1:])

        bus_r_gpio = Signal()
        self.comb += If(bus_r_gpio,
                bus.dat_r.eq(gpio)
            ).Else(
                bus.dat_r.eq(dr)
            )

        fud = Signal()
        if hasattr(pads, "fud"):
            self.sync += pads.fud.eq(fud)
        else:
            self.sync += pads.fud_n.eq(~fud)

        pads.wr_n.reset = 1
        pads.rd_n.reset = 1
        wr = Signal()
        rd = Signal()
        self.sync += pads.wr_n.eq(~wr), pads.rd_n.eq(~rd)

        self.submodules.read_timer = WaitTimer(read_wait_cycles)
        self.submodules.hiz_timer = WaitTimer(hiz_wait_cycles)

        fsm = FSM("IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            If(bus.cyc & bus.stb,
                If(bus.adr[flen(pads.a)],
                    If(bus.adr[0],
                        NextState("GPIO")
                    ).Else(
                        NextState("FUD")
                    )
                ).Else(
                    If(bus.we,
                        NextState("WRITE")
                    ).Else(
                        NextState("READ")
                    )
                )
            )
        )
        fsm.act("WRITE",
            # 3ns A setup to WR active
            wr.eq(1),
            NextState("WRITE0")
        )
        fsm.act("WRITE0",
            # 3.5ns D setup to WR inactive
            # 0ns D and A hold to WR inactive
            bus.ack.eq(1),
            NextState("IDLE")
        )
        fsm.act("READ",
            # 15ns D valid to A setup
            # 15ns D valid to RD active
            rx.eq(1),
            rd.eq(1),
            self.read_timer.wait.eq(1),
            If(self.read_timer.done,
               bus.ack.eq(1),
               NextState("WAIT_HIZ")
            )
        )
        fsm.act("WAIT_HIZ",
            rx.eq(1),
            # For some reason, AD9858 has an address hold time to RD inactive.
            hold_address.eq(1),
            self.hiz_timer.wait.eq(1),
            If(self.hiz_timer.done, NextState("IDLE"))
        )
        fsm.act("FUD",
            # 4ns FUD setup to SYNCLK
            # 0ns FUD hold to SYNCLK
            fud.eq(1),
            bus.ack.eq(1),
            NextState("IDLE")
        )
        fsm.act("GPIO",
            bus.ack.eq(1),
            bus_r_gpio.eq(1),
            If(bus.we, gpio_load.eq(1)),
            NextState("IDLE")
        )


def _test_gen():
    # Test external bus writes
    yield TWrite(4, 2)
    yield TWrite(5, 3)
    yield
    # Test external bus reads
    yield TRead(14)
    yield TRead(15)
    yield
    # Test FUD
    yield TWrite(64, 0)
    yield
    # Test GPIO
    yield TWrite(65, 0xff)
    yield


class _TestPads:
    def __init__(self):
        self.a = Signal(6)
        self.d = Signal(8)
        self.sel = Signal(5)
        self.fud_n = Signal()
        self.wr_n = Signal()
        self.rd_n = Signal()
        self.rst_n = Signal()


class _TB(Module):
    def __init__(self):
        pads = _TestPads()
        self.submodules.dut = AD9xxx(pads, drive_fud=True)
        self.submodules.initiator = wishbone.Initiator(_test_gen())
        self.submodules.interconnect = wishbone.InterconnectPointToPoint(
            self.initiator.bus, self.dut.bus)


if __name__ == "__main__":
    run_simulation(_TB(), vcd_name="ad9xxx.vcd")
