from migen import *
from migen.genlib.cdc import MultiReg
from misoc.interconnect.csr import *


class RTIOClockMultiplier(Module, AutoCSR):
    def __init__(self, rtio_clk_freq):
        self.pll_reset = CSRStorage(reset=1)
        self.pll_locked = CSRStatus()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        # See "Global Clock Network Deskew Using Two BUFGs" in ug472.
        clkfbout = Signal()
        clkfbin = Signal()
        rtiox4_clk = Signal()
        pll_locked = Signal()
        self.specials += [
            Instance("MMCME2_BASE",
                     p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                     i_CLKIN1=ClockSignal("rtio"),
                     i_RST=self.pll_reset.storage,
                     o_LOCKED=pll_locked,

                     p_CLKFBOUT_MULT_F=8.0, p_DIVCLK_DIVIDE=1,

                     o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbin,

                     p_CLKOUT0_DIVIDE_F=2.0, o_CLKOUT0=rtiox4_clk,
                     ),
            Instance("BUFG", i_I=clkfbout, o_O=clkfbin),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk),

            MultiReg(pll_locked, self.pll_locked.status)
        ]


def fix_serdes_timing_path(platform):
    # ignore timing of path from OSERDESE2 through the pad to ISERDESE2
    platform.add_platform_command(
        "set_false_path -quiet "
        "-through [get_pins -filter {{REF_PIN_NAME == OQ || REF_PIN_NAME == TQ}} "
            "-of [get_cells -filter {{REF_NAME == OSERDESE2}}]] "
        "-to [get_pins -filter {{REF_PIN_NAME == D}} "
            "-of [get_cells -filter {{REF_NAME == ISERDESE2}}]]"
    )
