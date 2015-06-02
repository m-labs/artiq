from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from targets.pipistrello import BaseSoC

from artiq.gateware.soc import AMPSoC
from artiq.gateware import rtio, ad9858, nist_qc1
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.rtio.phy.wishbone import RT2WB


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform):
        self._clock_sel = CSRStorage()
        self.clock_domains.cd_rtio = ClockDomain(reset_less=True)

        # 75MHz -> 125MHz
        rtio_internal_clk = Signal()
        self.specials += Instance("DCM_CLKGEN",
                                  p_CLKFXDV_DIVIDE=2,
                                  p_CLKFX_DIVIDE=3,
                                  p_CLKFX_MD_MAX=1.6,
                                  p_CLKFX_MULTIPLY=5,
                                  p_CLKIN_PERIOD=1e3/75,
                                  p_SPREAD_SPECTRUM="NONE",
                                  p_STARTUP_WAIT="FALSE",
                                  i_CLKIN=ClockSignal(),
                                  o_CLKFX=rtio_internal_clk,
                                  i_FREEZEDCM=0,
                                  i_RST=ResetSignal())

        rtio_external_clk = platform.request("dds_clock")
        platform.add_period_constraint(rtio_external_clk, 8.0)
        self.specials += Instance("BUFGMUX",
                                  i_I0=rtio_internal_clk,
                                  i_I1=rtio_external_clk,
                                  i_S=self._clock_sel.storage,
                                  o_O=self.cd_rtio.clk)

        platform.add_platform_command("""
NET "{int_clk}" TNM_NET = "GRPint_clk";
NET "{ext_clk}" TNM_NET = "GRPext_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSfix_ise1" = FROM "GRPint_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise2" = FROM "GRPsys_clk" TO "GRPint_clk" TIG;
TIMESPEC "TSfix_ise3" = FROM "GRPext_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise4" = FROM "GRPsys_clk" TO "GRPext_clk" TIG;
TIMESPEC "TSfix_ise5" = FROM "GRPext_clk" TO "GRPint_clk" TIG;
TIMESPEC "TSfix_ise6" = FROM "GRPint_clk" TO "GRPext_clk" TIG;
""", int_clk=rtio_internal_clk, ext_clk=rtio_external_clk)


class NIST_QC1(BaseSoC, AMPSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtio_crg": 13,
        "kernel_cpu": 14,
        "rtio_mon": 15
    }
    csr_map.update(BaseSoC.csr_map)
    mem_map = {
        "rtio":     0x20000000,  # (shadow @0xa0000000)
        "mailbox":  0x70000000   # (shadow @0xf0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform,
                         cpu_type=cpu_type, with_timer=False, **kwargs)
        AMPSoC.__init__(self)
        platform.toolchain.ise_commands += """
trce -v 12 -fastpaths -tsi {build_name}.tsi -o {build_name}.twr {build_name}.ncd {build_name}.pcf
"""
        platform.add_extension(nist_qc1.papilio_adapter_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1),
        ))

        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]

        # RTIO channels
        rtio_channels = []
        for i in range(2):
            phy = ttl_simple.Inout(platform.request("pmt", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel(phy.rtlink, phy.probes,
                                              ififo_depth=512))

        phy = ttl_simple.Inout(platform.request("xtrig", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink, phy.probes))

        for i in range(16):
            phy = ttl_simple.Output(platform.request("ttl", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel(phy.rtlink, phy.probes))

        phy = ttl_simple.Output(platform.request("ext_led", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink, phy.probes))

        for i in range(2, 5):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel(phy.rtlink, phy.probes))

        self.add_constant("RTIO_DDS_CHANNEL", len(rtio_channels))
        self.submodules.dds = RenameClockDomains(
            ad9858.AD9858(platform.request("dds")),
            "rio")
        phy = RT2WB(7, self.dds.bus)
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink, ififo_depth=4))

        # RTIO core
        self.submodules.rtio_crg = _RTIOCRG(platform)
        self.submodules.rtio = rtio.RTIO(rtio_channels,
                                         clk_freq=125000000)
        self.add_constant("RTIO_FINE_TS_WIDTH", self.rtio.fine_ts_width)
        self.submodules.rtio_mon = rtio.Monitor(rtio_channels)

        # CPU connections
        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["rtio"]),
                                     self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] | 0x80000000, 32,
                            rtio_csrs)


default_subtarget = NIST_QC1
