from migen.fhdl.std import *
from migen.genlib.fsm import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation


class WaitTimer(Module):
    def __init__(self, t):
        self.wait = Signal()
        self.done = Signal()

        # # #

        count = Signal(bits_for(t), reset=t)
        self.comb += self.done.eq(count == 0)
        self.sync += \
            If(self.wait,
                If(~self.done, count.eq(count - 1))
            ).Else(count.eq(count.reset))


class AD9858(Module):
    """Wishbone interface to the AD9858 DDS chip.

    Addresses 0-63 map the AD9858 registers.
    Data is zero-padded.

    Write to address 64 to pulse the FUD signal.
    Address 65 is a GPIO register that controls the sel, p and reset signals.
    sel is mapped to the lower bits, followed by p and reset.

    Write timing:
    Address is set one cycle before assertion of we_n.
    we_n is asserted for one cycle, at the same time as valid data is driven.

    Read timing:
    Address is set one cycle before assertion of rd_n.
    rd_n is asserted for 3 cycles.
    Data is sampled 2 cycles into the assertion of rd_n.

    Design:
    All IO pads are registered.

    LVDS driver/receiver propagation delays are 3.6+4.5 ns max
    LVDS state transition delays are 20, 15 ns max
    Schmitt trigger delays are 6.4ns max
    Round-trip addr A setup (> RX, RD, D to Z), RD prop, D valid (< D
    valid), D prop is ~15 + 10 + 20 + 10 = 55ns
    """
    def __init__(self, pads, drive_fud=False,
                 read_wait_cycles=10, hiz_wait_cycles=3,
                 bus=None):
        if bus is None:
            bus = wishbone.Interface()
        self.bus = bus

        # # #

        dts = TSTriple(8)
        self.specials += dts.get_tristate(pads.d)
        hold_address = Signal()
        dr = Signal(8)
        rx = Signal()
        self.sync += [
            If(~hold_address, pads.a.eq(bus.adr)),
            dts.o.eq(bus.dat_w),
            dr.eq(dts.i),
            dts.oe.eq(~rx)
        ]

        gpio = Signal(flen(pads.sel) + flen(pads.p) + 1)
        gpio_load = Signal()
        self.sync += If(gpio_load, gpio.eq(bus.dat_w))
        self.comb += [
            Cat(pads.sel, pads.p).eq(gpio),
            pads.rst_n.eq(~gpio[-1]),
        ]

        bus_r_gpio = Signal()
        self.comb += If(bus_r_gpio,
                bus.dat_r.eq(gpio)
            ).Else(
                bus.dat_r.eq(dr)
            )

        if drive_fud:
            fud = Signal()
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
                If(bus.adr[6],
                    If(bus.adr[0],
                        NextState("GPIO")
                    ).Else(
                        NextState("FUD") if drive_fud else None
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
            # For some reason, AD9858 has a address hold time to RD inactive.
            hold_address.eq(1),
            self.hiz_timer.wait.eq(1),
            If(self.hiz_timer.done, NextState("IDLE"))
        )
        if drive_fud:
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
        self.p = Signal(2)
        self.fud_n = Signal()
        self.wr_n = Signal()
        self.rd_n = Signal()
        self.rst_n = Signal()


class _TB(Module):
    def __init__(self):
        pads = _TestPads()
        self.submodules.dut = AD9858(pads, drive_fud=True)
        self.submodules.initiator = wishbone.Initiator(_test_gen())
        self.submodules.interconnect = wishbone.InterconnectPointToPoint(
            self.initiator.bus, self.dut.bus)


if __name__ == "__main__":
    run_simulation(_TB(), vcd_name="ad9858.vcd")
