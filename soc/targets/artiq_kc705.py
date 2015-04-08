from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen
from mibuild.generic_platform import *

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from targets.kc705 import BaseSoC

from artiq.gateware import amp, rtio, ad9858, nist_qc1


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


class _Peripherals(BaseSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform,
                         cpu_type=cpu_type, **kwargs)
        platform.add_extension(nist_qc1.fmc_adapter_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1)))

        fud = Signal()
        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]
        rtio_ins = [platform.request("pmt") for i in range(2)]
        rtio_outs = [platform.request("ttl", i) for i in range(16)]
        rtio_outs.append(platform.request("user_led", 2))
        self.add_constant("RTIO_FUD_CHANNEL", len(rtio_ins) + len(rtio_outs))
        rtio_outs.append(fud)

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


class UP(_Peripherals):
    def __init__(self, *args, **kwargs):
        _Peripherals.__init__(self, *args, **kwargs)

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
        _Peripherals.__init__(self, platform, *args, **kwargs)

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
