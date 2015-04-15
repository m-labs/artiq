from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from targets.pipistrello import BaseSoC

from artiq.gateware import amp, rtio, ad9858, nist_qc1
from artiq.gateware.rtio.phy import ttl_simple


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform):
        self._clock_sel = CSRStorage()
        self.clock_domains.cd_rtio = ClockDomain()

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


class _Peripherals(BaseSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13
    }
    csr_map.update(BaseSoC.csr_map)
    mem_map = {
        "rtio":     0x20000000,  # (shadow @0xa0000000)
        "dds":      0x50000000,  # (shadow @0xd0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform, cpu_type=cpu_type, **kwargs)
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
            rtio_channels.append(rtio.Channel(phy.rtlink, ififo_depth=512))

        phy = ttl_simple.Inout(platform.request("xtrig", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink))

        for i in range(16):
            phy = ttl_simple.Output(platform.request("ttl", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel(phy.rtlink))

        phy = ttl_simple.Output(platform.request("ext_led", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink))

        for i in range(2, 5):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel(phy.rtlink))

        fud = Signal()
        self.add_constant("RTIO_FUD_CHANNEL", len(rtio_channels))
        phy = ttl_simple.Output(fud)
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink))

        # RTIO core
        self.submodules.rtiocrg = _RTIOCRG(platform)
        self.submodules.rtio = rtio.RTIO(rtio_channels,
                                         clk_freq=125000000)

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.comb += dds_pads.fud_n.eq(~fud)


class UP(_Peripherals):
    def __init__(self, platform, **kwargs):
        _Peripherals.__init__(self, platform, **kwargs)

        rtio_csrs = self.rtio.get_csrs() + self.rtio.get_kernel_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.add_wb_slave(mem_decoder(self.mem_map["rtio"]), self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] + 0x80000000, 32,
                            rtio_csrs)

        self.add_wb_slave(mem_decoder(self.mem_map["dds"]), self.dds.bus)
        self.add_memory_region("dds", self.mem_map["dds"] + 0x80000000, 64*4)


class AMP(_Peripherals):
    csr_map = {
        "kernel_cpu": 14
    }
    csr_map.update(_Peripherals.csr_map)
    mem_map = {
        "mailbox":  0x70000000  # (shadow @0xf0000000)
    }
    mem_map.update(_Peripherals.mem_map)

    def __init__(self, platform, *args, **kwargs):
        _Peripherals.__init__(self, platform, **kwargs)

        self.submodules.kernel_cpu = amp.KernelCPU(
            platform, self.sdram.crossbar.get_master())
        self.submodules.mailbox = amp.Mailbox()
        self.add_wb_slave(mem_decoder(self.mem_map["mailbox"]),
                          self.mailbox.i1)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["mailbox"]),
                                     self.mailbox.i2)
        self.add_memory_region("mailbox",
                               self.mem_map["mailbox"] + 0x80000000, 4)

        rtio_csrs = self.rtio.get_kernel_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["rtio"]),
                                     self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] + 0x80000000, 32,
                            rtio_csrs)

        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["dds"]),
                                     self.dds.bus)
        self.add_memory_region("dds", self.mem_map["dds"] + 0x80000000, 64*4)


default_subtarget = AMP
