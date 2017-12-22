from math import ceil
from functools import reduce
from operator import add

from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.misc import WaitTimer


__all__ = ["BruteforceClockAligner", "GTHInit"]


class GTHInit(Module):
    def __init__(self, sys_clk_freq, rx):
        self.done = Signal()
        self.restart = Signal()

        # GTH signals
        self.plllock = Signal()
        self.pllreset = Signal()
        self.gtXxreset = Signal()
        self.Xxresetdone = Signal()
        self.Xxdlysreset = Signal()
        self.Xxdlysresetdone = Signal()
        self.Xxphaligndone = Signal()
        self.Xxsyncdone = Signal()
        self.Xxuserrdy = Signal()

        # # #

        # Double-latch transceiver asynch outputs
        plllock = Signal()
        Xxresetdone = Signal()
        Xxdlysresetdone = Signal()
        Xxphaligndone = Signal()
        Xxsyncdone = Signal()
        self.specials += [
            MultiReg(self.plllock, plllock),
            MultiReg(self.Xxresetdone, Xxresetdone),
            MultiReg(self.Xxdlysresetdone, Xxdlysresetdone),
            MultiReg(self.Xxphaligndone, Xxphaligndone),
            MultiReg(self.Xxsyncdone, Xxsyncdone)
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

        # PLL reset must be at least 2us
        pll_reset_cycles = ceil(2000*sys_clk_freq/1000000000)
        pll_reset_timer = WaitTimer(pll_reset_cycles)
        self.submodules += pll_reset_timer

        startup_fsm = ResetInserter()(FSM(reset_state="RESET_ALL"))
        self.submodules += startup_fsm

        ready_timer = WaitTimer(int(sys_clk_freq/1000))
        self.submodules += ready_timer
        self.comb += [
            ready_timer.wait.eq(~self.done & ~startup_fsm.reset),
            startup_fsm.reset.eq(self.restart | ready_timer.done)
        ]

        if rx:
            cdr_stable_timer = WaitTimer(1024)
            self.submodules += cdr_stable_timer

        Xxphaligndone_r = Signal(reset=1)
        Xxphaligndone_rising = Signal()
        self.sync += Xxphaligndone_r.eq(Xxphaligndone)
        self.comb += Xxphaligndone_rising.eq(Xxphaligndone & ~Xxphaligndone_r)

        startup_fsm.act("RESET_ALL",
            gtXxreset.eq(1),
            self.pllreset.eq(1),
            pll_reset_timer.wait.eq(1),
            If(pll_reset_timer.done,
                NextState("RELEASE_PLL_RESET")
            )
        )
        startup_fsm.act("RELEASE_PLL_RESET",
            gtXxreset.eq(1),
            If(plllock, NextState("RELEASE_GTH_RESET"))
        )
        # Release GTH reset and wait for GTH resetdone
        # (from UG476, GTH is reset on falling edge
        # of gtXxreset)
        if rx:
            startup_fsm.act("RELEASE_GTH_RESET",
                Xxuserrdy.eq(1),
                cdr_stable_timer.wait.eq(1),
                If(Xxresetdone & cdr_stable_timer.done, NextState("ALIGN"))
            )
        else:
            startup_fsm.act("RELEASE_GTH_RESET",
                Xxuserrdy.eq(1),
                If(Xxresetdone, NextState("ALIGN"))
            )
        # Start delay alignment (pulse)
        startup_fsm.act("ALIGN",
            Xxuserrdy.eq(1),
            Xxdlysreset.eq(1),
            NextState("WAIT_ALIGN")
        )
        if rx:
            # Wait for delay alignment
            startup_fsm.act("WAIT_ALIGN",
                Xxuserrdy.eq(1),
                If(Xxsyncdone,
                    NextState("READY")
                )
            )
        else:
            # Wait for delay alignment
            startup_fsm.act("WAIT_ALIGN",
                Xxuserrdy.eq(1),
                If(Xxdlysresetdone,
                    NextState("WAIT_FIRST_ALIGN_DONE")
                )
            )

        # Wait 2 rising edges of Xxphaligndone
        # (from UG576 in TX Buffer Bypass in Single-Lane Auto Mode)
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
            If(self.restart, NextState("RESET_ALL"))
        )


# Changes the phase of the transceiver RX clock to align the comma to
# the LSBs of RXDATA, fixing the latency.
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
#
# Warning: Xilinx transceivers are LSB first, and comma needs to be flipped
# compared to the usual 8b10b binary representation.
class BruteforceClockAligner(Module):
    def __init__(self, comma, tx_clk_freq, check_period=6e-3):
        self.rxdata = Signal(20)
        self.restart = Signal()

        self.ready = Signal()

        check_max_val = ceil(check_period*tx_clk_freq)
        check_counter = Signal(max=check_max_val+1)
        check = Signal()
        reset_check_counter = Signal()
        self.sync.rtio_tx += [
            check.eq(0),
            If(reset_check_counter,
                check_counter.eq(check_max_val)
            ).Else(
                If(check_counter == 0,
                    check.eq(1),
                    check_counter.eq(check_max_val)
                ).Else(
                    check_counter.eq(check_counter-1)
                )
            )
        ]

        checks_reset = PulseSynchronizer("rtio_tx", "rtio_rx")
        self.submodules += checks_reset

        comma_n = ~comma & 0b1111111111
        comma_seen_rxclk = Signal()
        comma_seen = Signal()
        comma_seen_rxclk.attr.add("no_retiming")
        self.specials += MultiReg(comma_seen_rxclk, comma_seen)
        self.sync.rtio_rx += \
            If(checks_reset.o,
                comma_seen_rxclk.eq(0)
            ).Elif((self.rxdata[:10] == comma) | (self.rxdata[:10] == comma_n),
                comma_seen_rxclk.eq(1)
            )

        error_seen_rxclk = Signal()
        error_seen = Signal()
        error_seen_rxclk.attr.add("no_retiming")
        self.specials += MultiReg(error_seen_rxclk, error_seen)
        rx1cnt = Signal(max=11)
        self.sync.rtio_rx += [
            rx1cnt.eq(reduce(add, [self.rxdata[i] for i in range(10)])),
            If(checks_reset.o,
                error_seen_rxclk.eq(0)
            ).Elif((rx1cnt != 4) & (rx1cnt != 5) & (rx1cnt != 6),
                error_seen_rxclk.eq(1)
            )
        ]

        fsm = ClockDomainsRenamer("rtio_tx")(FSM(reset_state="WAIT_COMMA"))
        self.submodules += fsm

        fsm.act("WAIT_COMMA",
            If(check,
                # Errors are still OK at this stage, as the transceiver
                # has just been reset and may output garbage data.
                If(comma_seen,
                    NextState("WAIT_NOERROR")
                ).Else(
                    self.restart.eq(1)
                ),
                checks_reset.i.eq(1)
            )
        )
        fsm.act("WAIT_NOERROR",
            If(check,
                If(comma_seen & ~error_seen,
                    NextState("READY")
                ).Else(
                    self.restart.eq(1),
                    NextState("WAIT_COMMA")
                ),
                checks_reset.i.eq(1)
            )
        )
        fsm.act("READY",
            reset_check_counter.eq(1),
            self.ready.eq(1),
            If(error_seen,
                checks_reset.i.eq(1),
                self.restart.eq(1),
                NextState("WAIT_COMMA")
            )
        )

