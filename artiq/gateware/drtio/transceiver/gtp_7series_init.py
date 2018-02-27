from math import ceil

from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.misc import WaitTimer


__all__ = ["GTPTXInit", "GTPRXInit"]


class GTPTXInit(Module):
    def __init__(self, sys_clk_freq, mode="single"):
        self.stable_clkin = Signal()
        self.done = Signal()
        self.restart = Signal()

        # GTP signals
        self.plllock = Signal()
        self.pllreset = Signal()
        self.gttxreset = Signal()
        self.gttxreset.attr.add("no_retiming")
        self.txresetdone = Signal()
        self.txdlysreset = Signal()
        self.txdlysresetdone = Signal()
        self.txphinit = Signal()
        self.txphinitdone = Signal()
        self.txphalign = Signal()
        self.txphaligndone = Signal()
        self.txdlyen = Signal()
        self.txuserrdy = Signal()

        self.master_phaligndone = Signal()
        self.slaves_phaligndone = Signal()

        # # #

        # Double-latch transceiver asynch outputs
        plllock = Signal()
        txresetdone = Signal()
        txdlysresetdone = Signal()
        txphinitdone = Signal()
        txphaligndone = Signal()
        self.specials += [
            MultiReg(self.plllock, plllock),
            MultiReg(self.txresetdone, txresetdone),
            MultiReg(self.txdlysresetdone, txdlysresetdone),
            MultiReg(self.txphinitdone, txphinitdone),
            MultiReg(self.txphaligndone, txphaligndone)
        ]

        # Deglitch FSM outputs driving transceiver asynch inputs
        gttxreset = Signal()
        txdlysreset = Signal()
        txphinit = Signal()
        txphalign = Signal()
        txdlyen = Signal()
        txuserrdy = Signal()
        self.sync += [
            self.gttxreset.eq(gttxreset),
            self.txdlysreset.eq(txdlysreset),
            self.txphinit.eq(txphinit),
            self.txphalign.eq(txphalign),
            self.txdlyen.eq(txdlyen),
            self.txuserrdy.eq(txuserrdy)
        ]

        # PLL reset must be at least 500us
        pll_reset_cycles = ceil(500e-9*sys_clk_freq)
        pll_reset_timer = WaitTimer(pll_reset_cycles)
        self.submodules += pll_reset_timer

        startup_fsm = ResetInserter()(FSM(reset_state="PLL_RESET"))
        self.submodules += startup_fsm

        ready_timer = WaitTimer(int(1e-3*sys_clk_freq))
        self.submodules += ready_timer
        self.comb += [
            ready_timer.wait.eq(~self.done & ~startup_fsm.reset),
            startup_fsm.reset.eq(self.restart | ready_timer.done)
        ]

        txphaligndone_r = Signal(reset=1)
        txphaligndone_rising = Signal()
        self.sync += txphaligndone_r.eq(txphaligndone)
        self.comb += txphaligndone_rising.eq(txphaligndone & ~txphaligndone_r)

        startup_fsm.act("PLL_RESET",
            self.pllreset.eq(1),
            pll_reset_timer.wait.eq(1),
            If(pll_reset_timer.done & self.stable_clkin,
                NextState("GTP_RESET")
            )
        )
        startup_fsm.act("GTP_RESET",
            gttxreset.eq(1),
            If(plllock,
                NextState("WAIT_GTP_RESET_DONE")
            )
        )
        # Release GTP reset and wait for GTP resetdone
        # (from UG482, GTP is reset on falling edge
        # of gttxreset)
        startup_fsm.act("WAIT_GTP_RESET_DONE",
            txuserrdy.eq(1),
            If(txresetdone, NextState("ALIGN"))
        )
        # Start delay alignment
        startup_fsm.act("ALIGN",
            txuserrdy.eq(1),
            txdlysreset.eq(1),
            If(txdlysresetdone,
                If(mode == "slave",
                    NextState("WAIT_MASTER")
                ).Else(
                    NextState("PHALIGN")
                )
            )
        )
        startup_fsm.act("WAIT_MASTER",
            txuserrdy.eq(1),
            If(self.master_phaligndone,
                NextState("PHALIGN")
            )
        )
        # Start phase alignment
        startup_fsm.act("PHALIGN",
            txuserrdy.eq(1),
            txphinit.eq(1),
            If(txphinitdone,
                NextState("WAIT_FIRST_ALIGN_DONE")
            )
        )
        # Wait N rising edges of Xxphaligndone
        # N=2 for Single, 3 for Master, 1 for Slave
        # (from UGB482 in TX Buffer Bypass in Multi/Single-Lane Auto Mode)
        startup_fsm.act("WAIT_FIRST_ALIGN_DONE",
            txuserrdy.eq(1),
            txphalign.eq(1),
            If(txphaligndone_rising,
                If(mode == "slave",
                    NextState("READY")
                ).Else(
                    NextState("WAIT_SECOND_ALIGN_DONE")
                )
            )
        )
        startup_fsm.act("WAIT_SECOND_ALIGN_DONE",
            txuserrdy.eq(1),
            txdlyen.eq(1),
            If(txphaligndone_rising,
                If(mode == "master",
                    NextState("WAIT_SLAVES")
                ).Else(
                    NextState("READY")
                )
            )
        )
        startup_fsm.act("WAIT_SLAVES",
            txuserrdy.eq(1),
            self.master_phaligndone.eq(1),
            If(self.slaves_phaligndone,
                NextState("WAIT_THIRD_ALIGN_DONE")
            )
        )
        startup_fsm.act("WAIT_THIRD_ALIGN_DONE",
            txuserrdy.eq(1),
            txdlyen.eq(1),
            If(txphaligndone_rising,
                NextState("READY")
            )
        )
        startup_fsm.act("READY",
            txuserrdy.eq(1),
            self.done.eq(1),
            If(self.restart, NextState("PLL_RESET"))
        )


class GTPRXInit(Module):
    def __init__(self, sys_clk_freq):
        self.done = Signal()
        self.restart = Signal()

        # GTP signals
        self.gtrxreset = Signal()
        self.gtrxreset.attr.add("no_retiming")
        self.gtrxpd = Signal()
        self.rxresetdone = Signal()
        self.rxdlysreset = Signal()
        self.rxdlysresetdone = Signal()
        self.rxphalign = Signal()
        self.rxdlyen = Signal()
        self.rxuserrdy = Signal()
        self.rxsyncdone = Signal()
        self.rxpmaresetdone = Signal()

        self.drpaddr = Signal(9)
        self.drpen = Signal()
        self.drpdi = Signal(16)
        self.drprdy = Signal()
        self.drpdo = Signal(16)
        self.drpwe = Signal()

        # # #

        drpvalue = Signal(16)
        drpmask = Signal()
        self.comb += [
            self.drpaddr.eq(0x011),
            If(drpmask,
                self.drpdi.eq(drpvalue & 0xf7ff)
            ).Else(
                self.drpdi.eq(drpvalue)
            )
        ]

        rxpmaresetdone = Signal()
        self.specials += MultiReg(self.rxpmaresetdone, rxpmaresetdone)
        rxpmaresetdone_r = Signal()
        self.sync += rxpmaresetdone_r.eq(rxpmaresetdone)

        # Double-latch transceiver asynch outputs
        rxresetdone = Signal()
        rxdlysresetdone = Signal()
        rxsyncdone = Signal()
        self.specials += [
            MultiReg(self.rxresetdone, rxresetdone),
            MultiReg(self.rxdlysresetdone, rxdlysresetdone),
            MultiReg(self.rxsyncdone, rxsyncdone)
        ]

        # Deglitch FSM outputs driving transceiver asynch inputs
        gtrxreset = Signal()
        gtrxpd = Signal()
        rxdlysreset = Signal()
        rxphalign = Signal()
        rxdlyen = Signal()
        rxuserrdy = Signal()
        self.sync += [
            self.gtrxreset.eq(gtrxreset),
            self.gtrxpd.eq(gtrxpd),
            self.rxdlysreset.eq(rxdlysreset),
            self.rxphalign.eq(rxphalign),
            self.rxdlyen.eq(rxdlyen),
            self.rxuserrdy.eq(rxuserrdy)
        ]

        startup_fsm = ResetInserter()(FSM(reset_state="GTP_PD"))
        self.submodules += startup_fsm

        ready_timer = WaitTimer(int(4e-3*sys_clk_freq))
        self.submodules += ready_timer
        self.comb += [
            ready_timer.wait.eq(~self.done & ~startup_fsm.reset),
            startup_fsm.reset.eq(self.restart | ready_timer.done)
        ]

        cdr_stable_timer = WaitTimer(1024)
        self.submodules += cdr_stable_timer

        startup_fsm.act("GTP_PD",
            gtrxpd.eq(1),
            NextState("GTP_RESET")
        )
        startup_fsm.act("GTP_RESET",
            gtrxreset.eq(1),
            NextState("DRP_READ_ISSUE")
        )
        startup_fsm.act("DRP_READ_ISSUE",
            gtrxreset.eq(1),
            self.drpen.eq(1),
            NextState("DRP_READ_WAIT")
        )
        startup_fsm.act("DRP_READ_WAIT",
            gtrxreset.eq(1),
            If(self.drprdy,
                NextValue(drpvalue, self.drpdo),
                NextState("DRP_MOD_ISSUE")
            )
        )
        startup_fsm.act("DRP_MOD_ISSUE",
            gtrxreset.eq(1),
            drpmask.eq(1),
            self.drpen.eq(1),
            self.drpwe.eq(1),
            NextState("DRP_MOD_WAIT")
        )
        startup_fsm.act("DRP_MOD_WAIT",
            gtrxreset.eq(1),
            If(self.drprdy,
                NextState("WAIT_PMARST_FALL")
            )
        )
        startup_fsm.act("WAIT_PMARST_FALL",
            rxuserrdy.eq(1),
            If(rxpmaresetdone_r & ~rxpmaresetdone,
                NextState("DRP_RESTORE_ISSUE")
            )
        )
        startup_fsm.act("DRP_RESTORE_ISSUE",
            rxuserrdy.eq(1),
            self.drpen.eq(1),
            self.drpwe.eq(1),
            NextState("DRP_RESTORE_WAIT")
        )
        startup_fsm.act("DRP_RESTORE_WAIT",
            rxuserrdy.eq(1),
            If(self.drprdy,
                NextState("WAIT_GTP_RESET_DONE")
            )
        )
        # Release GTP reset and wait for GTP resetdone
        # (from UG482, GTP is reset on falling edge
        # of gtrxreset)
        startup_fsm.act("WAIT_GTP_RESET_DONE",
            rxuserrdy.eq(1),
            cdr_stable_timer.wait.eq(1),
            If(rxresetdone & cdr_stable_timer.done,
                NextState("ALIGN")
            )
        )
        # Start delay alignment
        startup_fsm.act("ALIGN",
            rxuserrdy.eq(1),
            rxdlysreset.eq(1),
            If(rxdlysresetdone,
                NextState("WAIT_ALIGN_DONE")
            )
        )
        # Wait for delay alignment
        startup_fsm.act("WAIT_ALIGN_DONE",
            rxuserrdy.eq(1),
            If(rxsyncdone,
                NextState("READY")
            )
        )
        startup_fsm.act("READY",
            rxuserrdy.eq(1),
            self.done.eq(1),
            If(self.restart,
                NextState("GTP_PD")
            )
        )
