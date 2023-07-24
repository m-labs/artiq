from migen import *
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialOutput

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import spi2, ad53xx_monitor, dds, grabber
from artiq.gateware.suservo import servo, pads as servo_pads
from artiq.gateware.rtio.phy import servo as rtservo, fastino, phaser
from artiq.gateware.drtio.transceiver import eem_serdes
from artiq.gateware.shuttler.io_map import shuttler_fmc_ios

from pprint import pp

def _fmc_signal(i):
    n = "d{}".format(i)
    if i == 0:
        n += "_cc"
    return n


def _fmc_pin(fmc, i, pol):
    return "fmc{}:{}_{}".format(fmc, _fmc_signal(i), pol)


def default_iostandard():
    return IOStandard("LVDS_25")


class _FMC:
    @classmethod
    def add_extension(cls, target, fmc, *args, **kwargs):
        name = cls.__name__
        target.platform.add_extension(cls.io(fmc, *args, **kwargs))
        print("{} (FMC{}) starting at RTIO channel 0x{:06x}"
              .format(name, fmc, len(target.rtio_channels)))

class DIO(_FMC):
    @staticmethod
    def io(fmc, iostandard):
        return [("dio{}".format(fmc), i,
            Subsignal("p", Pins(_fmc_pin(fmc, i, "p"))),
            Subsignal("n", Pins(_fmc_pin(fmc, i, "n"))),
            iostandard(fmc))
            for i in range(8)]

    @classmethod
    def add_std(cls, target, fmc, ttl03_cls, ttl47_cls, iostandard=default_iostandard,
            edge_counter_cls=None):
        cls.add_extension(target, fmc, iostandard=iostandard)

        phys = []
        dci = iostandard(fmc).name == "LVDS"
        for i in range(4):
            pads = target.platform.request("dio{}".format(fmc), i)
            phy = ttl03_cls(pads.p, pads.n, dci=dci)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))
        for i in range(4):
            pads = target.platform.request("dio{}".format(fmc), 4+i)
            phy = ttl47_cls(pads.p, pads.n, dci=dci)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        if edge_counter_cls is not None:
            for phy in phys:
                state = getattr(phy, "input_state", None)
                if state is not None:
                    counter = edge_counter_cls(state)
                    target.submodules += counter
                    target.rtio_channels.append(rtio.Channel.from_phy(counter))


class DIO_SPI(_FMC):
    @staticmethod
    def io(fmc, spi, ttl, iostandard):
        def spi_subsignals(clk, mosi, miso, cs, pol):
            signals = [Subsignal("clk", Pins(_fmc_pin(fmc, clk, pol)))]
            if mosi is not None:
                signals.append(Subsignal("mosi",
                                         Pins(_fmc_pin(fmc, mosi, pol))))
            if miso is not None:
                signals.append(Subsignal("miso",
                                         Pins(_fmc_pin(fmc, miso, pol))))
            if cs:
                signals.append(Subsignal("cs_n", Pins(
                    *(_fmc_pin(fmc, pin, pol) for pin in cs))))
            return signals

        spi = [
            ("dio{}_spi{}_{}".format(fmc, i, pol), i,
             *spi_subsignals(clk, mosi, miso, cs, pol),
             iostandard(fmc))
            for i, (clk, mosi, miso, cs) in enumerate(spi) for pol in "pn"
        ]
        ttl = [
            ("dio{}".format(fmc), i,
             Subsignal("p", Pins(_fmc_pin(fmc, pin, "p"))),
             Subsignal("n", Pins(_fmc_pin(fmc, pin, "n"))),
             iostandard(fmc))
            for i, (pin, _, _) in enumerate(ttl)
        ]
        return spi + ttl

    @classmethod
    def add_std(cls, target, fmc, spi, ttl, iostandard=default_iostandard):
        cls.add_extension(target, fmc, spi, ttl, iostandard=iostandard)

        for i in range(len(spi)):
            phy = spi2.SPIMaster(
                target.platform.request("dio{}_spi{}_p".format(fmc, i)),
                target.platform.request("dio{}_spi{}_n".format(fmc, i))
            )
            target.submodules += phy
            target.rtio_channels.append(
                rtio.Channel.from_phy(phy, ififo_depth=4))

        dci = iostandard(fmc).name == "LVDS"
        for i, (_, ttl_cls, edge_counter_cls) in enumerate(ttl):
            pads = target.platform.request("dio{}".format(fmc), i)
            phy = ttl_cls(pads.p, pads.n, dci=dci)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

            if edge_counter_cls is not None:
                state = getattr(phy, "input_state", None)
                if state is not None:
                    counter = edge_counter_cls(state)
                    target.submodules += counter
                    target.rtio_channels.append(rtio.Channel.from_phy(counter))

class Shuttler(_FMC):
    @staticmethod
    def io(fmc=0, iostandard=default_iostandard):
        ios = shuttler_fmc_ios.fmc_io_map(fmc, iostandard)

        pp(ios)

        return ios

    # to be modified
    
    @classmethod
    def add_std(cls, target, fmc, ttl_out_cls, iostandard=default_iostandard):
        cls.add_extension(target, fmc, fmc_aux, iostandard=iostandard)

        # The following things should be instantiated
        # 1. I2C+GPIO for Clock Startup
        # 2. SPI for DAC Config
        # 3. Serdes for DAC

        # DAC SPI
        phy = spi2.SPIMaster(
                target.platform.request("shuttler{}_adc_spi_p".format(fmc))
                )
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))
        phy = spi2.SPIMaster(
                target.platform.request("shuttler{}_pgia_spi_p".format(fmc)),
                target.platform.request("shuttler{}_pgia_spi_n".format(fmc)))
        target.submodules += phy

        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))
        pads = target.platform.request("shuttler{}_cnv".format(fmc))
        phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += phy

        target.rtio_channels.append(rtio.Channel.from_phy(phy))
        sdr = target.platform.request("shuttler{}_sdr".format(fmc))
        target.specials += DifferentialOutput(1, sdr.p, sdr.n)
    