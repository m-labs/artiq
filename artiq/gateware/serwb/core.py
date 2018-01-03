from migen import *

from misoc.interconnect import stream

from artiq.gateware.serwb.scrambler import Scrambler, Descrambler
from artiq.gateware.serwb.packet import Packetizer, Depacketizer
from artiq.gateware.serwb.etherbone import Etherbone


class SERWBCore(Module):
    def __init__(self, phy, clk_freq, mode, with_scrambling=False):
        # etherbone
        self.submodules.etherbone = etherbone = Etherbone(mode)

        # packetizer / depacketizer
        depacketizer = Depacketizer(clk_freq)
        packetizer = Packetizer()
        self.submodules += depacketizer, packetizer

        # clock domain crossing
        tx_cdc = stream.AsyncFIFO([("data", 32)], 16)
        tx_cdc = ClockDomainsRenamer({"write": "sys", "read": phy.cd})(tx_cdc)
        rx_cdc = stream.AsyncFIFO([("data", 32)], 16)
        rx_cdc = ClockDomainsRenamer({"write": phy.cd, "read": "sys"})(rx_cdc)
        self.submodules += tx_cdc, rx_cdc

        # scrambling
        scrambler =  ClockDomainsRenamer(phy.cd)(Scrambler(enable=with_scrambling))
        descrambler = ClockDomainsRenamer(phy.cd)(Descrambler(enable=with_scrambling))
        self.submodules += scrambler, descrambler

        # modules connection
        self.comb += [
            # core --> phy
            packetizer.source.connect(tx_cdc.sink),
            tx_cdc.source.connect(scrambler.sink),
            If(phy.init.ready,
                If(scrambler.source.stb,
                    phy.serdes.tx_k.eq(scrambler.source.k),
                    phy.serdes.tx_d.eq(scrambler.source.d)
                ),
                scrambler.source.ack.eq(1)
            ),

            # phy --> core
            descrambler.sink.stb.eq(phy.init.ready),
            descrambler.sink.k.eq(phy.serdes.rx_k),
            descrambler.sink.d.eq(phy.serdes.rx_d),
            descrambler.source.connect(rx_cdc.sink),
            rx_cdc.source.connect(depacketizer.sink),

            # etherbone <--> core
            depacketizer.source.connect(etherbone.sink),
            etherbone.source.connect(packetizer.sink)
        ]
