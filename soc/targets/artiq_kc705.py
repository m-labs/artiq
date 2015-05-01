from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen
from mibuild.generic_platform import *
from mibuild.xilinx.vivado import XilinxVivadoToolchain

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from misoclib.cpu.peripherals import timer
from targets.kc705 import MiniSoC

from artiq.gateware.soc import AMPSoC
from artiq.gateware import rtio, ad9858, nist_qc1
from artiq.gateware.rtio.phy import ttl_simple


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk):
        self._clock_sel = CSRStorage()
        self.clock_domains.cd_rtio = ClockDomain()

        rtio_external_clk = Signal()
        user_sma_clock = platform.request("user_sma_clock")
        platform.add_period_constraint(user_sma_clock.p, 8.0)
        self.specials += Instance("IBUFDS",
                                  i_I=user_sma_clock.p, i_IB=user_sma_clock.n,
                                  o_O=rtio_external_clk)
        self.specials += Instance("BUFGMUX",
                                  i_I0=rtio_internal_clk,
                                  i_I1=rtio_external_clk,
                                  i_S=self._clock_sel.storage,
                                  o_O=self.cd_rtio.clk)


class NIST_QC1(MiniSoC, AMPSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13,
        "kernel_cpu": 14
    }
    csr_map.update(MiniSoC.csr_map)
    mem_map = {
        "rtio":     0x20000000, # (shadow @0xa0000000)
        "dds":      0x50000000, # (shadow @0xd0000000)
        "mailbox":  0x70000000  # (shadow @0xf0000000)
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        MiniSoC.__init__(self, platform,
                         cpu_type=cpu_type, with_timer=False, **kwargs)
        AMPSoC.__init__(self)
        platform.add_extension(nist_qc1.fmc_adapter_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1)))

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
        for i in range(16):
            phy = ttl_simple.Output(platform.request("ttl", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel(phy.rtlink))

        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink))

        fud = Signal()
        self.add_constant("RTIO_FUD_CHANNEL", len(rtio_channels))
        phy = ttl_simple.Output(fud)
        self.submodules += phy
        rtio_channels.append(rtio.Channel(phy.rtlink))

        # RTIO core
        self.submodules.rtiocrg = _RTIOCRG(platform, self.crg.pll_sys)
        self.submodules.rtio = rtio.RTIO(rtio_channels,
                                         clk_freq=125000000)

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.comb += dds_pads.fud_n.eq(~fud)

        if isinstance(platform.toolchain, XilinxVivadoToolchain):
            platform.add_platform_command("""
create_clock -name rsys_clk -period 8.0 [get_nets {rsys_clk}]
create_clock -name rio_clk -period 8.0 [get_nets {rio_clk}]
set_false_path -from [get_clocks rsys_clk] -to [get_clocks rio_clk]
set_false_path -from [get_clocks rio_clk] -to [get_clocks rsys_clk]
""", rsys_clk=self.rtio.cd_rsys.clk, rio_clk=self.rtio.cd_rio.clk)

        # CPU connections
        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["rtio"]),
                                     self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] | 0x80000000, 32,
                            rtio_csrs)

        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["dds"]),
                                     self.dds.bus)
        self.add_memory_region("dds", self.mem_map["dds"] | 0x80000000, 64*4)


default_subtarget = NIST_QC1
