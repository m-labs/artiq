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

        # fifos
        tx_fifo = stream.SyncFIFO([("data", 32)], 16)
        rx_fifo = stream.SyncFIFO([("data", 32)], 16)
        self.submodules += tx_fifo, rx_fifo

        # scrambling
        scrambler =  Scrambler(enable=with_scrambling)
        descrambler = Descrambler(enable=with_scrambling)
        self.submodules += scrambler, descrambler

        # modules connection
        self.comb += [
            # core --> phy
            packetizer.source.connect(tx_fifo.sink),
            tx_fifo.source.connect(scrambler.sink),
            If(phy.init.ready,
                If(scrambler.source.stb,
                    phy.serdes.tx_k.eq(scrambler.source.k),
                    phy.serdes.tx_d.eq(scrambler.source.d)
                ),
                scrambler.source.ack.eq(phy.serdes.tx_ce)
            ),

            # phy --> core
            If(phy.init.ready,
                descrambler.sink.stb.eq(phy.serdes.rx_ce),
                descrambler.sink.k.eq(phy.serdes.rx_k),
                descrambler.sink.d.eq(phy.serdes.rx_d)
            ),
			descrambler.source.connect(rx_fifo.sink),
            rx_fifo.source.connect(depacketizer.sink),

            # etherbone <--> core
            depacketizer.source.connect(etherbone.sink),
            etherbone.source.connect(packetizer.sink)
        ]
