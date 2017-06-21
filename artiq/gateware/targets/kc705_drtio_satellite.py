import argparse
import os

from migen import *
from migen.build.generic_platform import *
from misoc.cores import spi as spi_csr
from misoc.cores import gpio
from misoc.integration.builder import *
from misoc.integration.soc_core import mem_decoder
from misoc.targets.kc705 import BaseSoC, soc_kc705_args, soc_kc705_argdict

from artiq.gateware.ad9154_fmc_ebz import ad9154_fmc_ebz
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio import DRTIOSatellite
from artiq import __version__ as artiq_version
from artiq import __artiq_dir__ as artiq_dir


class Satellite(BaseSoC):
    mem_map = {
        "drtio_aux": 0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 ident=artiq_version,
                 **kwargs)

        platform = self.platform

        rtio_channels = []
        for i in range(8):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        for sma in "user_sma_gpio_p", "user_sma_gpio_n":
            phy = ttl_simple.InOut(platform.request(sma))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.comb += platform.request("sfp_tx_disable_n").eq(1)

        # 1000BASE_BX10 Ethernet compatible, 62.5MHz RTIO clock
        self.submodules.transceiver = gtx_7series.GTX_1000BASE_BX10(
            clock_pads=platform.request("si5324_clkout"),
            tx_pads=platform.request("sfp_tx"),
            rx_pads=platform.request("sfp_rx"),
            sys_clk_freq=self.clk_freq)
        self.submodules.rx_synchronizer = gtx_7series.RXSynchronizer(
            self.transceiver.rtio_clk_freq, initial_phase=180.0)
        self.submodules.drtio = DRTIOSatellite(
            self.transceiver, rtio_channels, self.rx_synchronizer)
        self.csr_devices.append("rx_synchronizer")
        self.csr_devices.append("drtio")
        self.add_wb_slave(mem_decoder(self.mem_map["drtio_aux"]),
                          self.drtio.aux_controller.bus)
        self.add_memory_region("drtio_aux", self.mem_map["drtio_aux"] | self.shadow_base, 0x800)

        self.config["RTIO_FREQUENCY"] = str(self.transceiver.rtio_clk_freq/1e6)
        si5324_clkin = platform.request("si5324_clkin")
        self.specials += \
            Instance("OBUFDS",
                i_I=ClockSignal("rtio_rx"),
                o_O=si5324_clkin.p, o_OB=si5324_clkin.n
            )
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None

        platform.add_extension(ad9154_fmc_ebz)
        ad9154_spi = platform.request("ad9154_spi")
        self.comb += ad9154_spi.en.eq(1)
        self.submodules.converter_spi = spi_csr.SPIMaster(ad9154_spi)
        self.csr_devices.append("converter_spi")

        self.comb += [
            platform.request("user_sma_clock_p").eq(ClockSignal("rtio_rx")),
            platform.request("user_sma_clock_n").eq(ClockSignal("rtio"))
        ]

        rtio_clk_period = 1e9/self.transceiver.rtio_clk_freq
        platform.add_period_constraint(self.transceiver.txoutclk, rtio_clk_period)
        platform.add_period_constraint(self.transceiver.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            platform.lookup_request("clk200"),
            self.transceiver.txoutclk, self.transceiver.rxoutclk)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / KC705 DRTIO satellite")
    builder_args(parser)
    soc_kc705_args(parser)
    args = parser.parse_args()

    soc = Satellite(**soc_kc705_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.add_software_package("satman", os.path.join(artiq_dir, "firmware", "satman"))
    builder.build()


if __name__ == "__main__":
    main()
