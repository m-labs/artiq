import logging

from migen import *

from . import spi


logger = logging.getLogger(__name__)


DDSParams = spi.SPIParams


class DDS(spi.SPISimple):
    """Multi-DDS SPI interface.

    * Supports SPI DDS chips like the AD9910.
    * Shifts data out to multiple DDS in parallel with a shared CLK and shared
      CS_N line.
    * Supports a single hardcoded command.
    * Configuration and setup must be done over a different channel.
    * Asserts IO_UPDATE for one clock cycle immediately after the SPI transfer.
    """
    def __init__(self, pads, params):
        super().__init__(pads, params)

        self.profile = [Signal(32 + 16 + 16, reset_less=True)
                for i in range(params.channels)]
        cmd = Signal(8, reset=0x0e)  # write to single tone profile 0
        assert params.width == len(cmd) + len(self.profile[0])

        self.sync += [
                If(self.start,
                    [d.eq(Cat(p, cmd))
                        for d, p in zip(self.data, self.profile)]
                )
        ]

        # this assumes that the cycle time (1/125 MHz = 8 ns) is >1 SYNC_CLK
        # cycle (1/250 MHz = 4ns)
        done_old = Signal()
        self.sync += done_old.eq(self.done)
        self.comb += pads.io_update.eq(self.done & ~done_old)
