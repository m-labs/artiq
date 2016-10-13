from math import ceil

from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.misc import WaitTimer
from migen.genlib.fsm import FSM


class GTXInit(Module):
    # Based on LiteSATA by Enjoy-Digital
    def __init__(self, sys_clk_freq, rx):
        self.done = Signal()
        self.restart = Signal()

        # GTX signals
        self.cplllock = Signal()
        self.gtXxreset = Signal()
        self.Xxresetdone = Signal()
        self.Xxdlysreset = Signal()
        self.Xxdlysresetdone = Signal()
        self.Xxphaligndone = Signal()
        self.Xxuserrdy = Signal()

        # # #

        # Double-latch transceiver asynch outputs
        cplllock = Signal()
        Xxresetdone = Signal()
        Xxdlysresetdone = Signal()
        Xxphaligndone = Signal()
        self.specials += [
            MultiReg(self.cplllock, cplllock),
            MultiReg(self.Xxresetdone, Xxresetdone),
            MultiReg(self.Xxdlysresetdone, Xxdlysresetdone),
            MultiReg(self.Xxphaligndone, Xxphaligndone),
        ]

        # Deglitch FSM outputs driving transceiver asynch inputs
        gtXxreset = Signal()
        Xxdlysreset = Signal()
        Xxuserrdy = Signal()
        self.sync += [
            self.gtXxreset.eq(gtXxreset),
            self.Xxdlysreset.eq(Xxdlysreset),
            self.Xxuserrdy.eq(Xxuserrdy)
        ]

        # After configuration, transceiver resets have to stay low for
        # at least 500ns (see AR43482)
        startup_cycles = ceil(500*sys_clk_freq/1000000000)
        startup_timer = WaitTimer(startup_cycles)
        self.submodules += startup_timer

        startup_fsm = FSM(reset_state="INITIAL")
        self.submodules += startup_fsm

        if rx:
            cdr_stable_timer = WaitTimer(1024)
            self.submodules += cdr_stable_timer

        Xxphaligndone_r = Signal(reset=1)
        Xxphaligndone_rising = Signal()
        self.sync += Xxphaligndone_r.eq(Xxphaligndone)
        self.comb += Xxphaligndone_rising.eq(Xxphaligndone & ~Xxphaligndone_r)

        startup_fsm.act("INITIAL",
            startup_timer.wait.eq(1),
            If(startup_timer.done, NextState("RESET_GTX"))
        )
        startup_fsm.act("RESET_GTX",
            gtXxreset.eq(1),
            NextState("WAIT_CPLL")
        )
        startup_fsm.act("WAIT_CPLL",
            gtXxreset.eq(1),
            If(cplllock, NextState("RELEASE_RESET"))
        )
        # Release GTX reset and wait for GTX resetdone
        # (from UG476, GTX is reset on falling edge
        # of gttxreset)
        if rx:
            startup_fsm.act("RELEASE_RESET",
                Xxuserrdy.eq(1),
                cdr_stable_timer.wait.eq(1),
                If(Xxresetdone & cdr_stable_timer.done, NextState("ALIGN"))
            )
        else:
            startup_fsm.act("RELEASE_RESET",
                Xxuserrdy.eq(1),
                If(Xxresetdone, NextState("ALIGN"))
            )
        # Start delay alignment (pulse)
        startup_fsm.act("ALIGN",
            Xxuserrdy.eq(1),
            Xxdlysreset.eq(1),
            NextState("WAIT_ALIGN")
        )
        # Wait for delay alignment
        startup_fsm.act("WAIT_ALIGN",
            Xxuserrdy.eq(1),
            If(Xxdlysresetdone, NextState("WAIT_FIRST_ALIGN_DONE"))
        )
        # Wait 2 rising edges of rxphaligndone
        # (from UG476 in buffer bypass config)
        startup_fsm.act("WAIT_FIRST_ALIGN_DONE",
            Xxuserrdy.eq(1),
            If(Xxphaligndone_rising, NextState("WAIT_SECOND_ALIGN_DONE"))
        )
        startup_fsm.act("WAIT_SECOND_ALIGN_DONE",
            Xxuserrdy.eq(1),
            If(Xxphaligndone_rising, NextState("READY"))
        )
        startup_fsm.act("READY",
            Xxuserrdy.eq(1),
            self.done.eq(1),
            If(self.restart, NextState("RESET_GTX"))
        )


# Changes the phase of the transceiver RX clock to align the comma to
# the MSBs of RXDATA, fixing the latency.
#
# This is implemented by repeatedly resetting the transceiver until it
# gives out the correct phase. Each reset gives a random phase.
#
# If Xilinx had designed the GTX transceiver correctly, RXSLIDE_MODE=PMA
# would achieve this faster and in a cleaner way. But:
#  * the phase jumps are of 2 UI at every second RXSLIDE pulse, instead
#    of 1 UI at every pulse. It is unclear what the latency becomes.
#  * RXSLIDE_MODE=PMA cannot be used with the RX buffer bypassed.
# Those design flaws make RXSLIDE_MODE=PMA yet another broken and useless
# transceiver "feature".
class BruteforceClockAligner(Module):
    def __init__(self, comma, sys_clk_freq, check_period=6e-3):
        self.rxdata = Signal(20)
        self.restart = Signal()

        check_max_val = ceil(check_period*sys_clk_freq)
        check_counter = Signal(max=check_max_val+1)
        check = Signal()
        self.sync += [
            check.eq(0),
            If(check_counter == 0,
                check.eq(1),
                check_counter.eq(check_max_val)
            ).Else(
                check_counter.eq(check_counter-1)
            )
        ]

        comma_n = ~comma & 0b1111111111
        comma_seen_rxclk = Signal()
        comma_seen = Signal()
        self.specials += MultiReg(comma_seen_rxclk, comma_seen)
        comma_seen_reset = PulseSynchronizer("sys", "rx")
        self.submodules += comma_seen_reset
        self.sync.rx += \
            If(comma_seen_reset.o,
                comma_seen_rxclk.eq(0)
            ).Elif((self.rxdata[:10] == comma) | (self.rxdata[:10] == comma_n),
                comma_seen_rxclk.eq(1)
            )

        self.comb += \
            If(check,
                If(~comma_seen, self.restart.eq(1)),
                comma_seen_reset.i.eq(1)
            )
