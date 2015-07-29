from fractions import Fraction

from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from misoclib.mem.sdram.core.minicon import MiniconSettings
from targets.pipistrello import BaseSoC

from artiq.gateware.soc import AMPSoC
from artiq.gateware import rtio, nist_qc1
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_spartan6, dds


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, clk_freq):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()

        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)
        self.clock_domains.cd_rtiox8 = ClockDomain(reset_less=True)
        self.rtiox4_stb = Signal()
        self.rtiox8_stb = Signal()

        rtio_f = 125*1000*1000
        f = Fraction(rtio_f, clk_freq)
        rtio_internal_clk = Signal()
        rtio_external_clk = Signal()
        pmt2 = platform.request("pmt", 2)
        dcm_locked = Signal()
        rtio_clk = Signal()
        pll_locked = Signal()
        pll = Signal(3)
        pll_fb = Signal()
        self.specials += [
            Instance("IBUFG", i_I=pmt2, o_O=rtio_external_clk),
            Instance("DCM_CLKGEN", p_CLKFXDV_DIVIDE=2,
                     p_CLKFX_DIVIDE=f.denominator, p_CLKFX_MD_MAX=float(f),
                     p_CLKFX_MULTIPLY=f.numerator, p_CLKIN_PERIOD=1e9/clk_freq,
                     p_SPREAD_SPECTRUM="NONE", p_STARTUP_WAIT="FALSE",
                     i_CLKIN=ClockSignal(), o_CLKFX=rtio_internal_clk,
                     i_FREEZEDCM=0, i_RST=ResetSignal(), o_LOCKED=dcm_locked),
            Instance("BUFGMUX",
                     i_I0=rtio_internal_clk, i_I1=rtio_external_clk,
                     i_S=self._clock_sel.storage, o_O=rtio_clk),
            Instance("PLL_ADV", p_SIM_DEVICE="SPARTAN6",
                     p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="INTERNAL",
                     p_REF_JITTER=.01, p_CLK_FEEDBACK="CLKFBOUT",
                     i_DADDR=0, i_DCLK=0, i_DEN=0, i_DI=0, i_DWE=0,
                     i_RST=self._pll_reset.storage | ~dcm_locked, i_REL=0,
                     p_DIVCLK_DIVIDE=1, p_CLKFBOUT_MULT=8,
                     p_CLKFBOUT_PHASE=0., i_CLKINSEL=1,
                     i_CLKIN1=rtio_clk, i_CLKIN2=0,
                     p_CLKIN1_PERIOD=1e9/rtio_f, p_CLKIN2_PERIOD=0.,
                     i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb, o_LOCKED=pll_locked,
                     o_CLKOUT0=pll[0], p_CLKOUT0_DUTY_CYCLE=.5,
                     o_CLKOUT1=pll[1], p_CLKOUT1_DUTY_CYCLE=.5,
                     o_CLKOUT2=pll[2], p_CLKOUT2_DUTY_CYCLE=.5,
                     p_CLKOUT0_PHASE=0., p_CLKOUT0_DIVIDE=1,
                     p_CLKOUT1_PHASE=0., p_CLKOUT1_DIVIDE=2,
                     p_CLKOUT2_PHASE=0., p_CLKOUT2_DIVIDE=8),
            Instance("BUFPLL", p_DIVIDE=8,
                     i_PLLIN=pll[0], i_GCLK=self.cd_rtio.clk,
                     i_LOCKED=pll_locked, o_IOCLK=self.cd_rtiox8.clk,
                     o_SERDESSTROBE=self.rtiox8_stb),
            Instance("BUFPLL", p_DIVIDE=4,
                     i_PLLIN=pll[1], i_GCLK=self.cd_rtio.clk,
                     i_LOCKED=pll_locked, o_IOCLK=self.cd_rtiox4.clk,
                     o_SERDESSTROBE=self.rtiox4_stb),
            Instance("BUFG", i_I=pll[2], o_O=self.cd_rtio.clk),
            AsyncResetSynchronizer(self.cd_rtio, ~pll_locked),
            MultiReg(pll_locked, self._pll_locked.status),
        ]

        # ISE infers correct period constraints for cd_rtio.clk from
        # the internal clock. The first two TIGs target just the BUFGMUX.
        platform.add_platform_command("""
NET "sys_clk" TNM_NET = "GRPsys_clk";
NET "{ext_clk}" TNM_NET = "GRPext_clk";
TIMESPEC "TSfix_ise1" = FROM "GRPsys_clk" TO "GRPext_clk" TIG;
NET "{int_clk}" TNM_NET = "GRPint_clk";
TIMESPEC "TSfix_ise2" = FROM "GRPsys_clk" TO "GRPint_clk" TIG;
NET "{rtio_clk}" TNM_NET = "GRPrtio_clk";
TIMESPEC "TSfix_ise3" = FROM "GRPrtio_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise4" = FROM "GRPsys_clk" TO "GRPrtio_clk" TIG;
""", ext_clk=rtio_external_clk, int_clk=rtio_internal_clk,
     rtio_clk=self.cd_rtio.clk)


class NIST_QC1(BaseSoC, AMPSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtio_crg": 13,
        "kernel_cpu": 14,
        "rtio_moninj": 15
    }
    csr_map.update(BaseSoC.csr_map)
    mem_map = {
        "rtio":     0x20000000,  # (shadow @0xa0000000)
        "mailbox":  0x70000000   # (shadow @0xf0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform,
                         cpu_type=cpu_type,
                         sdram_controller_settings=MiniconSettings(l2_size=64*1024),
                         with_timer=False, **kwargs)
        AMPSoC.__init__(self)
        platform.toolchain.ise_commands += """
trce -v 12 -fastpaths -tsi {build_name}.tsi -o {build_name}.twr {build_name}.ncd {build_name}.pcf
"""
        platform.add_extension(nist_qc1.papilio_adapter_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1),
            platform.request("user_led", 2),
            platform.request("user_led", 3),
        ))

        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]

        self.submodules.rtio_crg = _RTIOCRG(platform, self.clk_freq)

        # RTIO channels
        rtio_channels = []
        # pmt1 can run on a 8x serdes if pmt0 is not used
        for i in range(2):
            phy = ttl_serdes_spartan6.Inout_4X(platform.request("pmt", i),
                                               self.rtio_crg.rtiox4_stb)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512,
                                                       ofifo_depth=4))

        # ttl2 can run on a 8x serdes if xtrig is not used
        for i in range(15):
            if i in (0, 1):
                phy = ttl_serdes_spartan6.Output_4X(platform.request("ttl", i),
                                                    self.rtio_crg.rtiox4_stb)
            elif i in (2,):
                phy = ttl_serdes_spartan6.Output_8X(platform.request("ttl", i),
                                                    self.rtio_crg.rtiox8_stb)
            else:
                phy = ttl_simple.Output(platform.request("ttl", i))

            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=256))

        phy = ttl_simple.Output(platform.request("ext_led", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=4))

        phy = ttl_simple.Output(platform.request("user_led", 4))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=4))

        self.add_constant("RTIO_REGULAR_TTL_COUNT", len(rtio_channels))

        phy = ttl_simple.ClockGen(platform.request("ttl", 15))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.add_constant("RTIO_DDS_CHANNEL", len(rtio_channels))
        self.add_constant("DDS_CHANNEL_COUNT", 8)
        self.add_constant("DDS_AD9858")
        dds_pins = platform.request("dds")
        self.comb += dds_pins.p.eq(0)
        phy = dds.AD9858(dds_pins, 8)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy,
                                                   ofifo_depth=512,
                                                   ififo_depth=4))

        # RTIO core
        self.submodules.rtio = rtio.RTIO(rtio_channels)
        self.add_constant("RTIO_FINE_TS_WIDTH", self.rtio.fine_ts_width)
        self.add_constant("DDS_RTIO_CLK_RATIO", 8 >> self.rtio.fine_ts_width)
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)

        # CPU connections
        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["rtio"]),
                                     self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] | 0x80000000, 32,
                            rtio_csrs)


default_subtarget = NIST_QC1
