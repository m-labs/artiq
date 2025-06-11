from migen import *

from misoc.cores.spi2 import SPIMachine, SPIInterfaceXC7, SPIInterface
from artiq.gateware.rtio import rtlink


class SPIMaster(Module):
    """
    RTIO SPI Master version 2.

    Register address and bit map:

    data (address 0):
        32 write/read data

    config (address 1):
        1 offline: all pins high-z (reset=1)
        1 end: end transaction with next transfer (reset=1)
        1 input: submit read data on RTIO input when readable (reset=0)
        1 cs_polarity: active level of chip select (reset=0)
        1 clk_polarity: idle level of clk (reset=0)
        1 clk_phase: first edge after cs assertion to sample data on (reset=0)
            (clk_polarity, clk_phase) == (CPOL, CPHA) in Freescale language.
            (0, 0): idle low, output on falling, input on rising
            (0, 1): idle low, output on rising, input on falling
            (1, 0): idle high, output on rising, input on falling
            (1, 1): idle high, output on falling, input on rising
            There is never a clk edge during a cs edge.
        1 lsb_first: LSB is the first bit on the wire (reset=0)
        1 mosi_out_disable: 3-wire SPI, disable mosi output (reset=0)
        5 length: 1-32 bits = length + 1 (reset=0)
        3 padding
        8 div: counter load value to divide this module's clock
            to generate the SPI write clk (reset=0)
            f_clk/f_spi == div + 2
        8 cs: active high bit pattern of chip selects (reset=0)
    """
    def __init__(self, pads, pads_n=None):
        layout = [
            ("offline", 1),
            ("end", 1),
            ("input", 1),
            ("cs_polarity", 1),
            ("clk_polarity", 1),
            ("clk_phase", 1),
            ("lsb_first", 1),
            ("half_duplex", 1),
            ("length", 5),
            ("padding", 3),
            ("div", 8),
            ("cs", 8),
        ]

        config = Record(layout)

        config.offline.reset = 1
        config.end.reset = 1

        to_rio_phy = ClockDomainsRenamer("rio_phy")
        spi = to_rio_phy(SPIMachine(data_width=32, div_width=8))
        assert len(config) == len(spi.reg.pdo) == len(spi.reg.pdi) == 32

        if hasattr(pads, "mosi"):
            spi.reg.sdo.attr.add("iob")

        interface = to_rio_phy(SPIInterfaceXC7(pads, pads_n, sdo=spi.reg.sdo))
        self.submodules += interface, spi

        self.rtlink = rtlink.Interface(
                rtlink.OInterface(len(spi.reg.pdo), address_width=1,
                    enable_replace=False),
                rtlink.IInterface(len(spi.reg.pdi), timestamped=False)
        )

        ###

        read = Signal()

        data = Record(layout)
        self.comb += data.raw_bits().eq(self.rtlink.o.data)

        self.sync.rio_phy += [
            If(self.rtlink.i.stb,
                read.eq(0)
            ),
            If(self.rtlink.o.stb & spi.writable,
                If(self.rtlink.o.address,
                    config.raw_bits().eq(data.raw_bits()),
                ).Else(
                    read.eq(config.input)
                )
            ),
        ]

        self.comb += [
                spi.length.eq(config.length),
                spi.end.eq(config.end),
                spi.cg.div.eq(config.div),
                spi.clk_phase.eq(config.clk_phase),
                spi.reg.lsb_first.eq(config.lsb_first),

                interface.cs.eq(config.cs),
                interface.cs_polarity.eq(Replicate(
                    config.cs_polarity, len(interface.cs_polarity))),
                interface.clk_polarity.eq(config.clk_polarity),
                If(self.rtlink.o.stb & spi.writable & self.rtlink.o.address,
                    interface.half_duplex_next.eq(data.half_duplex),
                    interface.offline_next.eq(data.offline),
                ).Else(
                    interface.half_duplex_next.eq(config.half_duplex),
                    interface.offline_next.eq(config.offline),
                ),
                interface.cs_next.eq(spi.cs_next),
                interface.clk_next.eq(spi.clk_next),
                interface.ce.eq(spi.ce),
                interface.sample.eq(spi.reg.sample),
                spi.reg.sdi.eq(interface.sdi),

                spi.load.eq(self.rtlink.o.stb & spi.writable &
                    ~self.rtlink.o.address),
                spi.reg.pdo.eq(self.rtlink.o.data),
                self.rtlink.o.busy.eq(~spi.writable),
                self.rtlink.i.stb.eq(spi.readable & read),
                self.rtlink.i.data.eq(spi.reg.pdi)
        ]
        self.probes = []
