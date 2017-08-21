from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.misc import WaitTimer

from misoc.interconnect.csr import *


class PhaseDetector(Module, AutoCSR):
    def __init__(self, nbits=8):
        self.mdata = Signal(8)
        self.sdata = Signal(8)

        self.reset = Signal()
        self.too_early = Signal()
        self.too_late = Signal()

        # # #

        # Ideal sampling (middle of the eye):
        #  _____       _____       _____
        # |     |_____|     |_____|     |_____|   data
        #    +     +     +     +     +     +      master sampling
        #       -     -     -     -     -     -   slave sampling (90°/bit period)
        # Since taps are fixed length delays, this ideal case is not possible
        # and we will fall in the 2 following possible cases:
        #
        # 1) too late sampling (idelay needs to be decremented):
        #  _____       _____       _____
        # |     |_____|     |_____|     |_____|   data
        #     +     +     +     +     +     +     master sampling
        #        -     -     -     -     -     -  slave sampling (90°/bit period)
        # On mdata transition, mdata != sdata
        #
        #
        # 2) too early sampling (idelay needs to be incremented):
        #  _____       _____       _____
        # |     |_____|     |_____|     |_____|   data
        #   +     +     +     +     +     +       master sampling
        #      -     -     -     -     -     -    slave sampling (90°/bit period)
        # On mdata transition, mdata == sdata

        transition = Signal()
        inc = Signal()
        dec = Signal()

        # Find transition
        mdata_d = Signal(8)
        self.sync.serdes_5x += mdata_d.eq(self.mdata)
        self.comb += transition.eq(mdata_d != self.mdata)


        # Find what to do
        self.comb += [
            inc.eq(transition & (self.mdata == self.sdata)),
            dec.eq(transition & (self.mdata != self.sdata))
        ]

        # Error accumulator
        lateness = Signal(nbits, reset=2**(nbits - 1))
        too_late = Signal()
        too_early = Signal()
        reset_lateness = Signal()
        self.comb += [
            too_late.eq(lateness == (2**nbits - 1)),
            too_early.eq(lateness == 0)
        ]
        self.sync.serdes_5x += [
            If(reset_lateness,
                lateness.eq(2**(nbits - 1))
            ).Elif(~too_late & ~too_early,
                If(inc, lateness.eq(lateness - 1)),
                If(dec, lateness.eq(lateness + 1))
            )
        ]

        # control / status cdc
        self.specials += [
            MultiReg(too_early, self.too_early),
            MultiReg(too_late, self.too_late)
        ]
        self.submodules.do_reset_lateness = PulseSynchronizer("sys", "serdes_5x")
        self.comb += [
            reset_lateness.eq(self.do_reset_lateness.o),
            self.do_reset_lateness.i.eq(self.reset)
        ]


# Master <--> Slave synchronization:
# 1) Master sends idle pattern (zeroes) to reset Slave.
# 2) Master sends K28.5 commas to allow Slave to calibrate, Slave sends idle pattern.
# 3) Slave sends K28.5 commas to allow Master to calibrate, Master sends K28.5 commas.
# 4) Master stops sending K28.5 commas.
# 5) Slave stops sending K25.5 commas.
# 6) Link is ready.

class SerdesMasterInit(Module):
    def __init__(self, serdes, taps):
        self.reset = Signal()
        self.error = Signal()
        self.ready = Signal()

        # # #

        self.delay = delay = Signal(max=taps)
        self.delay_found = delay_found = Signal()
        self.bitslip = bitslip = Signal(max=40)
        self.bitslip_found = bitslip_found = Signal()

        timer = WaitTimer(8192)
        self.submodules += timer

        self.submodules.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += self.fsm.reset.eq(self.reset)

        phase_detector_too_early_last = Signal()

        fsm.act("IDLE",
            NextValue(delay_found, 0),
            NextValue(delay, 0),
            serdes.rx_delay_rst.eq(1),
            NextValue(bitslip_found, 0),
            NextValue(bitslip, 0),
            NextValue(phase_detector_too_early_last, 0),
            NextState("RESET_SLAVE"),
            serdes.tx_idle.eq(1)
        )
        fsm.act("RESET_SLAVE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("SEND_PATTERN")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("SEND_PATTERN",
            If(~serdes.rx_idle,
                NextState("WAIT_STABLE")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                serdes.phase_detector.reset.eq(1),
                If(~delay_found,
                    NextState("CHECK_PHASE")
                ).Else(
                    NextState("CHECK_PATTERN")
                ),
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CHECK_PHASE",
            # Since we are always incrementing delay,
            # ideal sampling  is found when phase detector
            # transitions from too_early to too_late
            If(serdes.phase_detector.too_late & 
                phase_detector_too_early_last,
                NextValue(delay_found, 1),
                NextState("CHECK_PATTERN")
            ).Elif(serdes.phase_detector.too_late |
                   serdes.phase_detector.too_early,
                NextValue(phase_detector_too_early_last, 
                          serdes.phase_detector.too_early),
                NextState("INC_DELAY")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("INC_DELAY",
            If(delay == (taps - 1),
                NextState("ERROR")
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1),
                serdes.rx_delay_ce.eq(1),
                NextState("WAIT_STABLE")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(serdes.rx_comma,
                timer.wait.eq(1),
                If(timer.done,
                    NextValue(bitslip_found, 1),
                    NextState("READY")
                )
            ).Else(
                NextState("INC_BITSLIP")
            ),
            serdes.tx_comma.eq(1)
        )
        self.comb += serdes.rx_bitslip_value.eq(bitslip)
        fsm.act("INC_BITSLIP",
            If(bitslip == (40 - 1),
                NextState("ERROR")
            ).Else(
                NextValue(bitslip, bitslip + 1),
                NextState("WAIT_STABLE")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        fsm.act("ERROR",
            self.error.eq(1)
        )


class SerdesSlaveInit(Module, AutoCSR):
    def __init__(self, serdes, taps):
        self.reset = Signal()
        self.ready = Signal()
        self.error = Signal()

        # # #

        self.delay = delay = Signal(max=taps)
        self.delay_found = delay_found = Signal()
        self.bitslip = bitslip = Signal(max=40)
        self.bitslip_found = bitslip_found = Signal()

        timer = WaitTimer(1024)
        self.submodules += timer

        self.comb += self.reset.eq(serdes.rx_idle)

        self.submodules.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))

        phase_detector_too_early_last = Signal()

        fsm.act("IDLE",
            NextValue(delay_found, 0),
            NextValue(delay, 0),
            serdes.rx_delay_rst.eq(1),
            NextValue(bitslip_found, 0),
            NextValue(bitslip, 0),
            NextValue(phase_detector_too_early_last, 0),
            NextState("WAIT_STABLE"),
            serdes.tx_idle.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                serdes.phase_detector.reset.eq(1),
                If(~delay_found,
                    NextState("CHECK_PHASE")
                ).Else(
                    NextState("CHECK_PATTERN")
                ),
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CHECK_PHASE",
            # Since we are always incrementing delay,
            # ideal sampling  is found when phase detector
            # transitions from too_early to too_late
            If(serdes.phase_detector.too_late & 
                phase_detector_too_early_last,
                NextValue(delay_found, 1),
                NextState("CHECK_PATTERN")
            ).Elif(serdes.phase_detector.too_late |
                   serdes.phase_detector.too_early,
                NextValue(phase_detector_too_early_last, 
                          serdes.phase_detector.too_early),
                NextState("INC_DELAY")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("INC_DELAY",
            If(delay == (taps - 1),
                NextState("ERROR")
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1),
                serdes.rx_delay_ce.eq(1),
                NextState("WAIT_STABLE")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(serdes.rx_comma,
                timer.wait.eq(1),
                If(timer.done,
                    NextValue(bitslip_found, 1),
                    NextState("SEND_PATTERN")
                )
            ).Else(
                NextState("INC_BITSLIP")
            ),
            serdes.tx_idle.eq(1)
        )
        self.comb += serdes.rx_bitslip_value.eq(bitslip)
        fsm.act("INC_BITSLIP",
            If(bitslip == (40 - 1),
                NextState("ERROR")
            ).Else(
                NextValue(bitslip, bitslip + 1),
                NextState("WAIT_STABLE")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("SEND_PATTERN",
            timer.wait.eq(1),
            If(timer.done,
                If(~serdes.rx_comma,
                    NextState("READY")
                )
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        fsm.act("ERROR",
            self.error.eq(1)
        )


class SerdesControl(Module, AutoCSR):
    def __init__(self, init, mode="master"):
        if mode == "master":
            self.reset = CSR()
        self.ready = CSRStatus()
        self.error = CSRStatus()

        self.delay = CSRStatus(9)
        self.delay_found = CSRStatus()
        self.bitslip = CSRStatus(6)
        self.bitslip_found = CSRStatus()

        # # #

        if mode == "master":
            self.comb += init.reset.eq(self.reset.re)
        self.comb += [
            self.ready.status.eq(init.ready),
            self.error.status.eq(init.error),
            self.delay_found.status.eq(init.delay_found),
            self.delay.status.eq(init.delay),
            self.bitslip_found.status.eq(init.bitslip_found),
            self.bitslip.status.eq(init.bitslip)
        ]
