from math import ceil
from functools import reduce
from operator import add

from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer


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

