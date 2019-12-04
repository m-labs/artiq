from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from misoc.interconnect.csr import *

from artiq.gateware.drtio.wrpll.si549 import Si549
from artiq.gateware.drtio.wrpll.ddmtd import DDMTD


class WRPLL(Module, AutoCSR):
    def __init__(self, helper_clk_pads, main_dcxo_i2c, helper_dxco_i2c, ddmtd_inputs, N=15):
        self.helper_reset = CSRStorage(reset=1)

        self.clock_domains.cd_helper = ClockDomain()
        self.helper_reset.storage.attr.add("no_retiming")
        self.specials += [
            Instance("IBUFGDS", i_I=helper_clk_pads.p, i_IB=helper_clk_pads.n,
                o_O=self.cd_helper.clk),
            AsyncResetSynchronizer(self.cd_helper, self.helper_reset.storage)
        ]

        self.submodules.main_dcxo = Si549(main_dcxo_i2c)
        self.submodules.helper_dcxo = Si549(helper_dxco_i2c)

        ddmtd_counter = Signal(N)
        self.sync.helper += ddmtd_counter.eq(ddmtd_counter + 1)
        self.submodules.ddmtd_helper = DDMTD(ddmtd_counter, ddmtd_inputs.rec_clk)
        self.submodules.ddmtd_main = DDMTD(ddmtd_counter, ddmtd_inputs.main_xo)
