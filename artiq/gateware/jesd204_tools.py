from collections import namedtuple

from migen import *
from migen.genlib.cdc import MultiReg, BusSynchronizer
from migen.genlib.resetsync import AsyncResetSynchronizer
from misoc.interconnect.csr import *

from jesd204b.common import (JESD204BTransportSettings,
                             JESD204BPhysicalSettings,
                             JESD204BSettings)
from jesd204b.phy.gth import (GTHChannelPLL as JESD204BGTHChannelPLL,
                              GTHQuadPLL as JESD204BGTHQuadPLL,
                              GTHTransmitter as JESD204BGTHTransmitter,
                              GTHInit as JESD204BGTHInit,
                              GTHTransmitterInterconnect as JESD204BGTHTransmitterInterconnect)
from jesd204b.phy import JESD204BPhyTX
from jesd204b.core import JESD204BCoreTX
from jesd204b.core import JESD204BCoreTXControl


class UltrascaleCRG(Module, AutoCSR):
    linerate = int(6e9)  # linerate = 20*data_rate*4/8 = data_rate*10
                          # data_rate = dac_rate/interp_factor
    refclk_freq = int(150e6)
    fabric_freq = int(125e6)

    def __init__(self, platform, use_rtio_clock=False):
        self.jreset = CSRStorage(reset=1)
        self.refclk = Signal()
        self.clock_domains.cd_jesd = ClockDomain()

        refclk2 = Signal()
        refclk_pads = platform.request("dac_refclk", 0)
        platform.add_period_constraint(refclk_pads.p, 1e9/self.refclk_freq)
        self.specials += [
            Instance("IBUFDS_GTE3", i_CEB=0, p_REFCLK_HROW_CK_SEL=0b00,
                     i_I=refclk_pads.p, i_IB=refclk_pads.n,
                     o_O=self.refclk, o_ODIV2=refclk2),
            AsyncResetSynchronizer(self.cd_jesd, self.jreset.storage),
        ]

        if use_rtio_clock:
            self.cd_jesd.clk.attr.add("keep")
            self.comb += self.cd_jesd.clk.eq(ClockSignal("rtio"))
        else:
            self.specials += Instance("BUFG_GT", i_I=refclk2, o_O=self.cd_jesd.clk)


PhyPads = namedtuple("PhyPads", "txp txn")


class UltrascaleTX(Module, AutoCSR):
    def __init__(self, platform, sys_crg, jesd_crg, dac, pll_type="cpll", tx_half=False):
        # Note: In general, the choice between channel and quad PLLs can be made based on the "nominal operating ranges", which are (see UG576, Ch.2):
        #  CPLL: 2.0 -  6.25  GHz
        # QPLL0: 9.8 - 16.375 GHz
        # QPLL1: 8.0 - 13.0   GHz
        # However, the exact frequency and/or linerate range should be checked according to the model and speed grade from their corresponding datasheets.
        pll_cls = {
            "cpll": JESD204BGTHChannelPLL,
            "qpll": JESD204BGTHQuadPLL
        }[pll_type]
        ps = JESD204BPhysicalSettings(l=8, m=4, n=16, np=16)
        ts = JESD204BTransportSettings(f=2, s=2, k=16, cs=0)
        settings = JESD204BSettings(ps, ts, did=0x5a, bid=0x5)

        jesd_pads = platform.request("dac_jesd", dac)
        plls = []
        phys = []
        for i in range(len(jesd_pads.txp)):
            pll = pll_cls(
                jesd_crg.refclk, jesd_crg.refclk_freq, jesd_crg.linerate)
            self.submodules += pll
            plls.append(pll)
        # QPLL quads
        if pll_type == "qpll":
            gthe3_common_cfgs = []
            for i in range(0, len(plls), 4):
                # GTHE3_COMMON common signals
                qpll_clk = Signal()
                qpll_refclk = Signal()
                qpll_reset = Signal()
                qpll_lock = Signal()
                # GTHE3_COMMON
                self.specials += pll_cls.get_gthe3_common(
                    jesd_crg.refclk, jesd_crg.refclk_freq, jesd_crg.linerate,
                    qpll_clk, qpll_refclk, qpll_reset, qpll_lock)
                gthe3_common_cfgs.append({
                    "clk": qpll_clk, 
                    "refclk": qpll_refclk,
                    "reset": qpll_reset,
                    "lock": qpll_lock
                })
        # Per-channel PLL phys
        for i, pll in enumerate(plls):
            # PhyTX
            phy = JESD204BPhyTX(
                pll, jesd_crg.refclk, PhyPads(jesd_pads.txp[i], jesd_pads.txn[i]),
                jesd_crg.fabric_freq, transceiver="gth", tx_half=tx_half)
            phys.append(phy)
            if tx_half:
                platform.add_period_constraint(phy.transmitter.cd_tx_half.clk,
                    80*1e9/jesd_crg.linerate)
                platform.add_false_path_constraints(
                    sys_crg.cd_sys.clk,
                    jesd_crg.cd_jesd.clk,
                    phy.transmitter.cd_tx_half.clk)
            else:
                platform.add_period_constraint(phy.transmitter.cd_tx.clk,
                    40*1e9/jesd_crg.linerate)
                platform.add_false_path_constraints(
                    sys_crg.cd_sys.clk,
                    jesd_crg.cd_jesd.clk,
                    phy.transmitter.cd_tx.clk)
        # CHANNEL & init interconnects
        for i, (pll, phy) in enumerate(zip(plls, phys)):
            # CPLLs: 1 init per channel
            if pll_type == "cpll":
                phy_channel_cfg = {}
                # Connect reset/lock to init
                pll_reset = pll.reset
                pll_lock = pll.lock
                self.submodules += JESD204BGTHTransmitterInterconnect(
                    pll_reset, pll_lock, phy.transmitter, phy.transmitter.init)
            # QPLL: 4 inits and 4 channels per quad
            elif pll_type == "qpll":
                # Connect clk/refclk to CHANNEL
                phy_cfg = gthe3_common_cfgs[int(i//4)]
                phy_channel_cfg = {
                    "qpll_clk": phy_cfg["clk"],
                    "qpll_refclk": phy_cfg["refclk"]
                }
                # Connect reset/lock to init
                pll_reset = phy_cfg["reset"]
                pll_lock = phy_cfg["lock"]
                if i % 4 == 0:
                    self.submodules += JESD204BGTHTransmitterInterconnect(
                        pll_reset, pll_lock, phy.transmitter, 
                        [phys[j].transmitter.init for j in range(i, min(len(phys), i+4))])
            # GTHE3_CHANNEL
            self.specials += JESD204BGTHTransmitter.get_gthe3_channel(
                    pll, phy.transmitter, **phy_channel_cfg)

        self.submodules.core = JESD204BCoreTX(
            phys, settings, converter_data_width=64)
        self.submodules.control = JESD204BCoreTXControl(self.core)
        self.core.register_jsync(platform.request("dac_sync", dac))


class DDMTDEdgeDetector(Module):
    def __init__(self, i):
        self.rising = Signal()

        history = Signal(4)
        deglitched = Signal()
        self.sync.helper += history.eq(Cat(history[1:], i))
        self.comb += deglitched.eq(i | history[0] | history[1] | history[2] | history[3])

        deglitched_r = Signal()
        self.sync.helper += [
            deglitched_r.eq(deglitched),
            self.rising.eq(deglitched & ~deglitched_r)
        ]


# See "Digital femtosecond time difference circuit for CERN's timing system"
# by P. Moreira and I. Darwazeh
class DDMTD(Module, AutoCSR):
    def __init__(self, input_pads, rtio_clk_freq=150e6):
        N = 64
        self.reset = CSRStorage(reset=1)
        self.locked = CSRStatus()
        self.dt = CSRStatus(N.bit_length())

        # # #

        self.clock_domains.cd_helper = ClockDomain(reset_less=True)
        helper_locked = Signal()
        helper_fb = Signal()
        helper_output = Signal()

        input_se = Signal()
        beat1 = Signal()
        beat2 = Signal()
        self.specials += [
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                i_CLKIN1=ClockSignal("rtio"),
                i_RST=self.reset.storage,
                o_LOCKED=helper_locked,

                # VCO at 1200MHz with 150MHz RTIO frequency
                p_CLKFBOUT_MULT_F=8.0,
                p_DIVCLK_DIVIDE=1,

                o_CLKFBOUT=helper_fb, i_CLKFBIN=helper_fb,

                # helper PLL ratio: 64/65 (N=64)
                p_CLKOUT0_DIVIDE_F=8.125,
                o_CLKOUT0=helper_output,
            ),
            MultiReg(helper_locked, self.locked.status),
            Instance("BUFG", i_I=helper_output, o_O=self.cd_helper.clk),
            Instance("IBUFDS", i_I=input_pads.p, i_IB=input_pads.n, o_O=input_se),
            Instance("FD", i_C=self.cd_helper.clk, i_D=input_se, o_Q=beat1, attr={("IOB", "TRUE")}),
            Instance("FD", i_C=self.cd_helper.clk, i_D=ClockSignal("rtio"), o_Q=beat2),
        ]

        ed1 = DDMTDEdgeDetector(beat1)
        ed2 = DDMTDEdgeDetector(beat2)
        self.submodules += ed1, ed2

        counting = Signal()
        counter = Signal(N.bit_length())
        result = Signal.like(counter)
        self.sync.helper += [
            If(counting,
                counter.eq(counter + 1)
            ).Else(
                result.eq(counter)
            ),

            If(ed1.rising, counting.eq(1), counter.eq(0)),
            If(ed2.rising, counting.eq(0))
        ]

        bsync = BusSynchronizer(len(result), "helper", "sys")
        self.submodules += bsync
        self.comb += [
            bsync.i.eq(result),
            self.dt.status.eq(bsync.o)
        ]


# This assumes:
#  * fine RTIO frequency (rtiox) = 2*RTIO frequency
#  * JESD and coarse RTIO clocks are the same
#    (only reset may differ).
class SysrefSampler(Module, AutoCSR):
    def __init__(self, sysref_pads, coarse_ts, sysref_phase_bits=8):
        self.sh_error = CSRStatus()
        self.sh_error_reset = CSRStorage()
        # Note: only the lower log2(RTIO frequency / SYSREF frequency) bits are stable
        self.sysref_phase = CSRStatus(8)

        self.jref = Signal()

        # # #

        sysref_se = Signal()
        sysref_oversample = Signal(4)
        self.specials += [
            Instance("IBUFDS", i_I=sysref_pads.p, i_IB=sysref_pads.n, o_O=sysref_se),
            Instance("ISERDESE3",
                p_IS_CLK_INVERTED=0,
                p_IS_CLK_B_INVERTED=1,
                p_DATA_WIDTH=4,

                i_D=sysref_se,
                i_RST=ResetSignal("rtio"),
                i_FIFO_RD_EN=0,
                i_CLK=ClockSignal("rtiox"),
                i_CLK_B=ClockSignal("rtiox"), # locally inverted
                i_CLKDIV=ClockSignal("rtio"),
                o_Q=sysref_oversample)
        ]

        self.comb += self.jref.eq(sysref_oversample[1])
        sh_error = Signal()
        sh_error_reset = Signal()
        self.sync.rtio += [
            If(~(  (sysref_oversample[0] == sysref_oversample[1])
                 & (sysref_oversample[1] == sysref_oversample[2])),
                sh_error.eq(1)
            ),
            If(sh_error_reset, sh_error.eq(0))
        ]
        self.specials += [
            MultiReg(self.sh_error_reset.storage, sh_error_reset, "rtio"),
            MultiReg(sh_error, self.sh_error.status)
        ]

        jref_r = Signal()
        sysref_phase_rtio = Signal(sysref_phase_bits)
        self.sync.rtio += [
            jref_r.eq(self.jref),
            If(self.jref & ~jref_r, sysref_phase_rtio.eq(coarse_ts))
        ]
        sysref_phase_rtio.attr.add("no_retiming")
        self.specials += MultiReg(sysref_phase_rtio, self.sysref_phase.status)
