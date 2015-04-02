from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen
from mibuild.generic_platform import *

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from targets.kc705 import BaseSoC

from artiq.gateware import amp, rtio, ad9858


_tester_io = [
    ("pmt", 0, Pins("LPC:LA20_N"), IOStandard("LVTTL")),
    ("pmt", 1, Pins("LPC:LA24_P"), IOStandard("LVTTL")),

    ("ttl", 0, Pins("LPC:LA21_P"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("LPC:LA25_P"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("LPC:LA21_N"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("LPC:LA25_N"), IOStandard("LVTTL")),
    ("ttl", 4, Pins("LPC:LA22_P"), IOStandard("LVTTL")),
    ("ttl", 5, Pins("LPC:LA26_P"), IOStandard("LVTTL")),
    ("ttl", 6, Pins("LPC:LA22_N"), IOStandard("LVTTL")),
    ("ttl", 7, Pins("LPC:LA26_N"), IOStandard("LVTTL")),
    ("ttl", 8, Pins("LPC:LA23_P"), IOStandard("LVTTL")),
    ("ttl", 9, Pins("LPC:LA27_P"), IOStandard("LVTTL")),
    ("ttl", 10, Pins("LPC:LA23_N"), IOStandard("LVTTL")),
    ("ttl", 11, Pins("LPC:LA27_N"), IOStandard("LVTTL")),
    ("ttl", 12, Pins("LPC:LA00_CC_P"), IOStandard("LVTTL")),
    ("ttl", 13, Pins("LPC:LA10_P"), IOStandard("LVTTL")),
    ("ttl", 14, Pins("LPC:LA00_CC_N"), IOStandard("LVTTL")),
    ("ttl", 15, Pins("LPC:LA10_N"), IOStandard("LVTTL")),
    ("ttl_l_tx_en", 0, Pins("LPC:LA11_P"), IOStandard("LVTTL")),
    ("ttl_h_tx_en", 0, Pins("LPC:LA01_CC_P"), IOStandard("LVTTL")),

    ("dds", 0,
        Subsignal("a", Pins("LPC:LA04_N LPC:LA14_N LPC:LA05_P LPC:LA15_P "
                            "LPC:LA05_N LPC:LA15_N")),
        Subsignal("d", Pins("LPC:LA06_P LPC:LA16_P LPC:LA06_N LPC:LA16_N "
                            "LPC:LA07_P LPC:LA17_CC_P LPC:LA07_N "
                            "LPC:LA17_CC_N")),
        Subsignal("sel", Pins("LPC:LA12_N LPC:LA03_P LPC:LA13_P LPC:LA03_N "
                              "LPC:LA13_N")),
        Subsignal("p", Pins("LPC:LA11_N LPC:LA02_P")),
        Subsignal("fud_n", Pins("LPC:LA14_P")),
        Subsignal("wr_n", Pins("LPC:LA04_P")),
        Subsignal("rd_n", Pins("LPC:LA02_N")),
        Subsignal("rst_n", Pins("LPC:LA12_P")),
        IOStandard("LVTTL")),
]


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk):
        self._r_clock_sel = CSRStorage()
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
                                  i_S=self._r_clock_sel.storage,
                                  o_O=self.cd_rtio.clk)


class _ARTIQSoCPeripherals(BaseSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform,
                         cpu_type=cpu_type, **kwargs)
        platform.add_extension(_tester_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1)))

        fud = Signal()
        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]
        rtio_ins = [platform.request("pmt") for i in range(2)]
        rtio_outs = [platform.request("ttl", i) for i in range(6)] + [fud]

        self.submodules.rtiocrg = _RTIOCRG(platform, self.crg.pll_sys)
        self.submodules.rtiophy = rtio.phy.SimplePHY(
            rtio_ins + rtio_outs,
            output_only_pads=set(rtio_outs))
        self.submodules.rtio = rtio.RTIO(self.rtiophy,
                                         clk_freq=125000000,
                                         ififo_depth=512)

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.comb += dds_pads.fud_n.eq(~fud)


class ARTIQSoCBasic(_ARTIQSoCPeripherals):
    def __init__(self, *args, **kwargs):
        _ARTIQSoCPeripherals.__init__(self, *args, **kwargs)

        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.add_wb_slave(mem_decoder(0xa0000000), self.rtiowb.bus)
        self.add_csr_region("rtio", 0xa0000000, 32, rtio_csrs)

        self.add_wb_slave(mem_decoder(0xb0000000), self.dds.bus)


class ARTIQSoC(_ARTIQSoCPeripherals):
    csr_map = {
        "kernel_cpu": 14
    }
    csr_map.update(_ARTIQSoCPeripherals.csr_map)

    def __init__(self, platform, *args, **kwargs):
        _ARTIQSoCPeripherals.__init__(self, platform, *args, **kwargs)

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


default_subtarget = ARTIQSoCBasic
