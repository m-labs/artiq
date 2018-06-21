from collections import namedtuple

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer
from misoc.interconnect.csr import *

from jesd204b.common import (JESD204BTransportSettings,
                             JESD204BPhysicalSettings,
                             JESD204BSettings)
from jesd204b.phy.gth import GTHChannelPLL as JESD204BGTHChannelPLL
from jesd204b.phy import JESD204BPhyTX
from jesd204b.core import JESD204BCoreTX
from jesd204b.core import JESD204BCoreTXControl


class UltrascaleCRG(Module, AutoCSR):
    linerate = int(6e9)
    refclk_freq = int(150e6)
    fabric_freq = int(125e6)

    def __init__(self, platform, use_rtio_clock=False):
        self.jreset = CSRStorage(reset=1)
        self.jref = Signal()
        self.refclk = Signal()
        self.clock_domains.cd_jesd = ClockDomain()

        refclk2 = Signal()
        refclk_pads = platform.request("dac_refclk", 1)
        platform.add_period_constraint(refclk_pads.p, 1e9/self.refclk_freq)
        self.specials += [
            Instance("IBUFDS_GTE3", i_CEB=self.jreset.storage, p_REFCLK_HROW_CK_SEL=0b00,
                     i_I=refclk_pads.p, i_IB=refclk_pads.n,
                     o_O=self.refclk, o_ODIV2=refclk2),
            AsyncResetSynchronizer(self.cd_jesd, self.jreset.storage),
        ]

        if use_rtio_clock:
            self.comb += self.cd_jesd.clk.eq(ClockSignal("rtio"))
        else:
            self.specials += Instance("BUFG_GT", i_I=refclk2, o_O=self.cd_jesd.clk)

        jref = platform.request("dac_sysref")
        jref_se = Signal()
        self.specials += [
            Instance("IBUFDS_IBUFDISABLE",
                p_USE_IBUFDISABLE="TRUE", p_SIM_DEVICE="ULTRASCALE",
                i_IBUFDISABLE=self.jreset.storage,
                i_I=jref.p, i_IB=jref.n,
                o_O=jref_se),
            # SYSREF normally meets s/h at the FPGA, except during margin
            # scan and before full initialization.
            # Be paranoid and use a double-register anyway.
            MultiReg(jref_se, self.jref, "jesd")
        ]


PhyPads = namedtuple("PhyPads", "txp txn")


class UltrascaleTX(Module, AutoCSR):
    def __init__(self, platform, sys_crg, jesd_crg, dac):
        ps = JESD204BPhysicalSettings(l=8, m=4, n=16, np=16)
        ts = JESD204BTransportSettings(f=2, s=2, k=16, cs=0)
        settings = JESD204BSettings(ps, ts, did=0x5a, bid=0x5)

        jesd_pads = platform.request("dac_jesd", dac)
        phys = []
        for i in range(len(jesd_pads.txp)):
            cpll = JESD204BGTHChannelPLL(
                    jesd_crg.refclk, jesd_crg.refclk_freq, jesd_crg.linerate)
            self.submodules += cpll
            phy = JESD204BPhyTX(
                    cpll, PhyPads(jesd_pads.txp[i], jesd_pads.txn[i]),
                    jesd_crg.fabric_freq, transceiver="gth")
            platform.add_period_constraint(phy.transmitter.cd_tx.clk,
                    40*1e9/jesd_crg.linerate)
            platform.add_false_path_constraints(
                sys_crg.cd_sys.clk,
                jesd_crg.cd_jesd.clk,
                phy.transmitter.cd_tx.clk)
            phys.append(phy)

        to_jesd = ClockDomainsRenamer("jesd")
        self.submodules.core = core = to_jesd(JESD204BCoreTX(
            phys, settings, converter_data_width=64))
        self.submodules.control = control = to_jesd(JESD204BCoreTXControl(core))
        core.register_jsync(platform.request("dac_sync", dac))
        core.register_jref(jesd_crg.jref)


# This assumes:
#  * coarse RTIO frequency = 16*SYSREF frequency
#  * JESD and coarse RTIO clocks are the same
#    (only reset may differ).
#  * SYSREF meets setup/hold at the FPGA when sampled
#    in the JESD/RTIO domain.
#
# Look at the 4 LSBs of the coarse RTIO timestamp counter
# to determine SYSREF phase.

class SysrefSampler(Module, AutoCSR):
    def __init__(self, coarse_ts, jref):
        self.sample_result = CSRStatus()

        sample = Signal()
        self.sync.rtio += If(coarse_ts[:4] == 0, sample.eq(jref))
        self.specials += MultiReg(sample, self.sample_result.status)
