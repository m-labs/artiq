from math import ceil

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer
from migen.genlib.fsm import FSM


class GTXInit(Module):
    # Based on LiteSATA by Enjoy-Digital
    # Choose between Auto Mode and Manual Mode for TX/RX phase alignment with buffer bypassed:
    # * Auto Mode: When only single lane is involved, as suggested by Xilinx (AR59612)
    # * Manual Mode: When only multi-lane is involved, as suggested by Xilinx (AR59612)
    def __init__(self, sys_clk_freq, rx, mode="single"):
        assert isinstance(rx, bool)
        assert mode in ["single", "master", "slave"]
        self.mode = mode

        self.done = Signal()
        self.restart = Signal()

        # GTX signals
        self.cplllock = Signal()
        self.cpllreset = Signal()
        self.gtXxreset = Signal()
        self.Xxresetdone = Signal()
        self.Xxdlysreset = Signal()
        self.Xxdlysresetdone = Signal()
        self.Xxphaligndone = Signal()
        self.Xxuserrdy = Signal()
        # GTX signals exclusive to multi-lane 
        if mode != "single":
            self.Xxphalign = Signal()
            self.Xxdlyen = Signal()
            # TX only:
            if not rx:
                self.txphinit = Signal()
                self.txphinitdone = Signal()

        # Strobe from master channel to initialize TX/RX phase alignment on slaves
        self.master_phaligndone = Signal()
        # Strobe from slave channels to re-enable TX/RX delay alignment on master;
        # To be combinatorially AND-ed from all slave's `done`
        if mode == "master":
            self.slaves_phaligndone = Signal()

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
        if mode != "single":
            txphinitdone = Signal()
            self.specials += MultiReg(self.txphinitdone, txphinitdone)

        # Deglitch FSM outputs driving transceiver asynch inputs
        gtXxreset = Signal()
        Xxdlysreset = Signal()
        Xxuserrdy = Signal()
        self.sync += [
            self.gtXxreset.eq(gtXxreset),
            self.Xxdlysreset.eq(Xxdlysreset),
            self.Xxuserrdy.eq(Xxuserrdy)
        ]
        if mode != "single":
            Xxphalign = Signal()
            Xxdlyen = Signal()
            self.sync += [
                self.Xxphalign.eq(Xxphalign),
                self.Xxdlyen.eq(Xxdlyen)
            ]
            if not rx:
                txphinit = Signal()
                self.sync += self.txphinit.eq(txphinit)

        # After configuration, transceiver resets have to stay low for
        # at least 500ns (see AR43482)
        startup_cycles = ceil(500*sys_clk_freq/1000000000)
        startup_timer = WaitTimer(startup_cycles)
        self.submodules += startup_timer

        # PLL reset should be 1 period of refclk
        # (i.e. 1/(125MHz) for the case of RTIO @ 125MHz)
        pll_reset_cycles = ceil(sys_clk_freq/125e6)
        pll_reset_timer = WaitTimer(pll_reset_cycles)
        self.submodules += pll_reset_timer

        startup_fsm = FSM(reset_state="INITIAL")
        self.submodules += startup_fsm

        if rx:
            cdr_stable_timer = WaitTimer(1024)
            self.submodules += cdr_stable_timer

        # Rising edge detection for phase alignment "done"
        Xxphaligndone_r = Signal(reset=1)
        Xxphaligndone_rising = Signal()
        self.sync += Xxphaligndone_r.eq(Xxphaligndone)
        self.comb += Xxphaligndone_rising.eq(Xxphaligndone & ~Xxphaligndone_r)

        startup_fsm.act("INITIAL",
            startup_timer.wait.eq(1),
            If(startup_timer.done, NextState("RESET_ALL"))
        )
        startup_fsm.act("RESET_ALL",
            gtXxreset.eq(1),
            self.cpllreset.eq(1),
            pll_reset_timer.wait.eq(1),
            If(pll_reset_timer.done, NextState("RELEASE_PLL_RESET"))
        )
        startup_fsm.act("RELEASE_PLL_RESET",
            gtXxreset.eq(1),
            If(cplllock, NextState("RELEASE_GTH_RESET"))
        )
        # Release GTX reset and wait for GTX resetdone
        # (from UG476, GTX is reset on falling edge
        # of gttxreset)
        if rx:
            startup_fsm.act("RELEASE_GTH_RESET",
                Xxuserrdy.eq(1),
                cdr_stable_timer.wait.eq(1),
                If(Xxresetdone & cdr_stable_timer.done, NextState("DELAY_ALIGN"))
            )
        else:
            startup_fsm.act("RELEASE_GTH_RESET",
                Xxuserrdy.eq(1),
                If(Xxresetdone, NextState("DELAY_ALIGN"))
            )

        # States exclusive to Auto Mode:
        if mode == "single":
            # Start delay alignment (pulse)
            startup_fsm.act("DELAY_ALIGN",
                Xxuserrdy.eq(1),
                Xxdlysreset.eq(1),
                NextState("WAIT_DELAY_ALIGN")
            )
            # Wait for delay alignment
            startup_fsm.act("WAIT_DELAY_ALIGN",
                Xxuserrdy.eq(1),
                If(Xxdlysresetdone, NextState("WAIT_FIRST_PHASE_ALIGN_DONE"))
            )
            # Wait 2 rising edges of rxphaligndone
            # (from UG476 in buffer bypass config)
            startup_fsm.act("WAIT_FIRST_PHASE_ALIGN_DONE",
                Xxuserrdy.eq(1),
                If(Xxphaligndone_rising, NextState("WAIT_SECOND_PHASE_ALIGN_DONE"))
            )
            startup_fsm.act("WAIT_SECOND_PHASE_ALIGN_DONE",
                Xxuserrdy.eq(1),
                If(Xxphaligndone_rising, NextState("READY"))
            )

        # States exclusive to Manual Mode:
        else:
            # Start delay alignment (hold)
            startup_fsm.act("DELAY_ALIGN",
                Xxuserrdy.eq(1),
                Xxdlysreset.eq(1),
                If(Xxdlysresetdone,
                    # TX master: proceed to initialize phase alignment manually
                    (NextState("PHASE_ALIGN_INIT") if not rx else
                    # RX master: proceed to start phase alignment manually
                    NextState("PHASE_ALIGN")) if mode == "master" else
                    # TX/RX slave: wait for phase alignment "done" on master
                    NextState("WAIT_MASTER")
                )
            )
            if mode == "slave":
                # TX slave: Wait for phase alignment "done" on master
                startup_fsm.act("WAIT_MASTER",
                    Xxuserrdy.eq(1),
                    If(self.master_phaligndone,
                        # TX slave: proceed to initialize phase alignment manually
                        NextState("PHASE_ALIGN_INIT") if not rx else
                        # RX slave: proceed to start phase alignment manually
                        NextState("PHASE_ALIGN")
                    )
                )
            if not rx:
                # TX master/slave: Initialize phase alignment, wait rising edge on "done"
                startup_fsm.act("PHASE_ALIGN_INIT",
                    Xxuserrdy.eq(1),
                    txphinit.eq(1),
                    If(txphinitdone, NextState("PHASE_ALIGN"))
                )
            # Do phase ealignment, wait rising edge on "done"
            startup_fsm.act("PHASE_ALIGN",
                Xxuserrdy.eq(1),
                Xxphalign.eq(1),
                If(Xxphaligndone_rising,
                    # TX/RX master: proceed to set T/RXDLYEN
                    NextState("FIRST_DLYEN") if mode == "master" else
                    # TX/RX slave: proceed to signal master
                    NextState("READY")
                )
            )
            if mode == "master":
                # Enable delay alignment in manual mode, wait rising edge on phase alignment "done"
                startup_fsm.act("FIRST_DLYEN",
                    Xxuserrdy.eq(1),
                    Xxdlyen.eq(1),
                    If(Xxphaligndone_rising, NextState("WAIT_SLAVES"))
                )
                # Wait for phase alignment "done" on all slaves
                startup_fsm.act("WAIT_SLAVES",
                    Xxuserrdy.eq(1),
                    self.master_phaligndone.eq(1),
                    If(self.slaves_phaligndone, NextState("SECOND_DLYEN"))
                )
                # Re-enable delay alignment in manual mode, wait rising edge on phase alignment "done"
                startup_fsm.act("SECOND_DLYEN",
                    Xxuserrdy.eq(1),
                    Xxdlyen.eq(1),
                    If(Xxphaligndone_rising, NextState("READY"))
                )

        # Transceiver is ready, alignment can be restarted
        startup_fsm.act("READY",
            Xxuserrdy.eq(1),
            self.done.eq(1),
            If(self.restart, NextState("RESET_ALL"))
        )


class GTXInitPhaseAlignment(Module):
    # Interconnect of phase alignment "done" signals for Manual Mode multi-lane
    def __init__(self, gtx_inits):
        master_phaligndone = Signal()   # Fan-out to `slave.master_phaligndone`s
        slaves_phaligndone = Signal(reset=1)   # ANDed from `slave.done`s
        # Slave channels
        for gtx_init in gtx_inits:
            if gtx_init.mode == "slave":
                self.comb += gtx_init.master_phaligndone.eq(master_phaligndone)
                slaves_phaligndone = slaves_phaligndone & gtx_init.done
        # Master channels
        for gtx_init in gtx_inits:
            if gtx_init.mode == "master":
                self.comb += [
                    master_phaligndone.eq(gtx_init.master_phaligndone),
                    gtx_init.slaves_phaligndone.eq(slaves_phaligndone)
                ]
