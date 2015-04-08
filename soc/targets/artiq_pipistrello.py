from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from targets.pipistrello import BaseSoC

from artiq.gateware import amp, rtio, ad9858, nist_qc1


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
NET "{rtio_clk}" TNM_NET = "GRPrtio_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSfix_ise1" = FROM "GRPrtio_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise2" = FROM "GRPsys_clk" TO "GRPrtio_clk" TIG;
""", rtio_clk=rtio_internal_clk)


class _Peripherals(BaseSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform, cpu_type=cpu_type, **kwargs)
        platform.add_extension(nist_qc1.papilio_adapter_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1),
        ))

        fud = Signal()
        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]
        rtio_ins = [platform.request("pmt", i) for i in range(2)]
        rtio_ins += [platform.request("xtrig", 0)]
        rtio_outs = [platform.request("ttl", i) for i in range(16)]
        rtio_outs += [platform.request("ext_led", 0)]
        rtio_outs += [platform.request("user_led", i) for i in range(2, 5)]
        self.add_constant("RTIO_FUD_CHANNEL", len(rtio_ins) + len(rtio_outs))
        rtio_outs.append(fud)

        self.submodules.rtiocrg = _RTIOCRG(platform)
        self.submodules.rtiophy = rtio.phy.SimplePHY(
            rtio_ins + rtio_outs,
            output_only_pads=set(rtio_outs))
        self.submodules.rtio = rtio.RTIO(self.rtiophy,
                                         clk_freq=125000000,
                                         ififo_depth=512)

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.comb += dds_pads.fud_n.eq(~fud)


class UP(_Peripherals):
    def __init__(self, platform, **kwargs):
        _Peripherals.__init__(self, platform, **kwargs)

        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.add_wb_slave(mem_decoder(0xa0000000), self.rtiowb.bus)
        self.add_csr_region("rtio", 0xa0000000, 32, rtio_csrs)

        self.add_wb_slave(mem_decoder(0xb0000000), self.dds.bus)


class AMP(_Peripherals):
    csr_map = {
        "kernel_cpu": 14
    }
    csr_map.update(_Peripherals.csr_map)

    def __init__(self, platform, *args, **kwargs):
        _Peripherals.__init__(self, platform, **kwargs)

        self.submodules.kernel_cpu = amp.KernelCPU(
            platform, self.sdram.crossbar.get_master())
        self.submodules.mailbox = amp.Mailbox()
        self.add_wb_slave(mem_decoder(0xd0000000), self.mailbox.i1)
        self.kernel_cpu.add_wb_slave(mem_decoder(0xd0000000), self.mailbox.i2)

        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.kernel_cpu.add_wb_slave(mem_decoder(0xa0000000), self.rtiowb.bus)
        self.add_csr_region("rtio", 0xa0000000, 32, rtio_csrs)

        self.kernel_cpu.add_wb_slave(mem_decoder(0xb0000000), self.dds.bus)


default_subtarget = UP
