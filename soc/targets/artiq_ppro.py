from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen
from mibuild.generic_platform import *

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from misoclib.mem.sdram.core.minicon import MiniconSettings
from targets.ppro import BaseSoC

from artiq.gateware import rtio, ad9858, nist_qc1


class _TestGen(Module):
    def __init__(self, pad):
        divc = Signal(15)
        ce = Signal()
        self.sync += Cat(divc, ce).eq(divc + 1)

        sr = Signal(8, reset=0b10101000)
        self.sync += If(ce, sr.eq(Cat(sr[1:], sr[0])))
        self.comb += pad.eq(sr[0])


class _RTIOMiniCRG(Module, AutoCSR):
    def __init__(self, platform):
        self._clock_sel = CSRStorage()
        self.clock_domains.cd_rtio = ClockDomain()

        # 80MHz -> 125MHz
        rtio_internal_clk = Signal()
        self.specials += Instance("DCM_CLKGEN",
            p_CLKFXDV_DIVIDE=2,
            p_CLKFX_DIVIDE=16, p_CLKFX_MD_MAX=1.6, p_CLKFX_MULTIPLY=25,
            p_CLKIN_PERIOD=12.5, p_SPREAD_SPECTRUM="NONE",
            p_STARTUP_WAIT="FALSE",

            i_CLKIN=ClockSignal(), o_CLKFX=rtio_internal_clk,
            i_FREEZEDCM=0, i_RST=ResetSignal())

        rtio_external_clk = platform.request("xtrig")
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


class UP(BaseSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13
    }
    csr_map.update(BaseSoC.csr_map)
    mem_map = {
        "rtio":     0x20000000, # (shadow @0xa0000000)
        "dds":      0x50000000, # (shadow @0xd0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, cpu_type="or1k",
                 with_test_gen=False, **kwargs):
        BaseSoC.__init__(self, platform,
                         cpu_type=cpu_type,
                         sdram_controller_settings=MiniconSettings(),
                         **kwargs)
        platform.add_extension(nist_qc1.papilio_adapter_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("ext_led", 0)))

        fud = Signal()
        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]
        rtio_ins = [platform.request("pmt") for i in range(2)]
        rtio_outs = [platform.request("ttl", i) for i in range(5)]
        self.add_constant("RTIO_FUD_CHANNEL", len(rtio_ins) + len(rtio_outs))
        rtio_outs.append(fud)

        self.submodules.rtiocrg = _RTIOMiniCRG(platform)
        self.submodules.rtiophy = rtio.phy.SimplePHY(
            rtio_ins + rtio_outs,
            output_only_pads=set(rtio_outs))
        self.submodules.rtio = rtio.RTIO(self.rtiophy,
                                         clk_freq=125000000,
                                         counter_width=32,
                                         ififo_depth=512)

        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.add_wb_slave(mem_decoder(self.mem_map["rtio"]), self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] + 0x80000000, 32, rtio_csrs)

        if with_test_gen:
            self.submodules.test_gen = _TestGen(platform.request("ttl", 8))

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.add_wb_slave(mem_decoder(self.mem_map["dds"]), self.dds.bus)
        self.add_memory_region("dds", self.mem_map["dds"] + 0x80000000, 64*4)
        self.comb += dds_pads.fud_n.eq(~fud)


default_subtarget = UP
