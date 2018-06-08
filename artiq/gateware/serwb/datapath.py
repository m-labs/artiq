from migen import *
from migen.genlib.io import *
from migen.genlib.misc import BitSlip, WaitTimer

from misoc.interconnect import stream
from misoc.cores.code_8b10b import Encoder, Decoder

from artiq.gateware.serwb.scrambler import Scrambler, Descrambler


def K(x, y):
    return (y << 5) | x


class _8b10bEncoder(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint([("d", 32), ("k", 4)])
        self.source = source = stream.Endpoint([("data", 40)])

        # # #

        encoder = CEInserter()(Encoder(4, True))
        self.submodules += encoder

        # control
        self.comb += [
            source.stb.eq(sink.stb),
            sink.ack.eq(source.ack),
            encoder.ce.eq(source.stb & source.ack)
        ]

        # datapath
        for i in range(4):
            self.comb += [
                encoder.k[i].eq(sink.k[i]),
                encoder.d[i].eq(sink.d[8*i:8*(i+1)]),
                source.data[10*i:10*(i+1)].eq(encoder.output[i])
            ]


class _8b10bDecoder(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint([("data", 40)])
        self.source = source = stream.Endpoint([("d", 32), ("k", 4)])

        # # #

        decoders = [CEInserter()(Decoder(True)) for _ in range(4)]
        self.submodules += decoders

        # control
        self.comb += [
            source.stb.eq(sink.stb),
            sink.ack.eq(source.ack)
        ]
        self.comb += [decoders[i].ce.eq(source.stb & source.ack) for i in range(4)]

        # datapath
        for i in range(4):
            self.comb += [
                decoders[i].input.eq(sink.data[10*i:10*(i+1)]),
                source.k[i].eq(decoders[i].k),
                source.d[8*i:8*(i+1)].eq(decoders[i].d)
            ]


class _Bitslip(Module):
    def __init__(self):
        self.value = value = Signal(6)
        self.sink = sink = stream.Endpoint([("data", 40)])
        self.source = source = stream.Endpoint([("data", 40)])

        # # #

        bitslip = CEInserter()(BitSlip(40))
        self.submodules += bitslip

        # control
        self.comb += [
            source.stb.eq(sink.stb),
            sink.ack.eq(source.ack),
            bitslip.value.eq(value),
            bitslip.ce.eq(source.stb & source.ack)
        ]

        # datapath
        self.comb += [
            bitslip.i.eq(sink.data),
            source.data.eq(bitslip.o)
        ]


class TXDatapath(Module):
    def __init__(self, phy_dw, with_scrambling=True):
        self.idle = idle = Signal()
        self.comma = comma = Signal()
        self.sink = sink = stream.Endpoint([("data", 32)])
        self.source = source = stream.Endpoint([("data", phy_dw)])

        # # #

        # scrambler
        if with_scrambling:
            self.submodules.scrambler = scrambler = Scrambler()

        # line coding
        self.submodules.encoder = encoder = _8b10bEncoder()

        # converter
        self.submodules.converter = converter = stream.Converter(40, phy_dw)

        # dataflow
        if with_scrambling:
            self.comb += [
                sink.connect(scrambler.sink),
                If(comma,
                    encoder.sink.stb.eq(1),
                    encoder.sink.k.eq(1),
                    encoder.sink.d.eq(K(28,5))
                ).Else(
                    scrambler.source.connect(encoder.sink)
                )
            ]
        else:
            self.comb += [
                If(comma,
                    encoder.sink.stb.eq(1),
                    encoder.sink.k.eq(1),
                    encoder.sink.d.eq(K(28,5))
                ).Else(
                    sink.connect(encoder.sink, omit={"data"}),
                    encoder.sink.d.eq(sink.data)
                ),
            ]
        self.comb += [
            If(idle,
                converter.sink.stb.eq(1),
                converter.sink.data.eq(0)
            ).Else(
                encoder.source.connect(converter.sink),
            ),
            converter.source.connect(source)
        ]


class RXDatapath(Module):
    def __init__(self, phy_dw, with_scrambling=True):
        self.bitslip_value = bitslip_value = Signal(6)
        self.sink = sink = stream.Endpoint([("data", phy_dw)])
        self.source = source = stream.Endpoint([("data", 32)])
        self.idle = idle = Signal()
        self.comma = comma = Signal()

        # # #

        # converter
        self.submodules.converter = converter = stream.Converter(phy_dw, 40)

        # bitslip
        self.submodules.bitslip = bitslip = _Bitslip()
        self.comb += bitslip.value.eq(bitslip_value)

        # line coding
        self.submodules.decoder = decoder = _8b10bDecoder()

        # descrambler
        if with_scrambling:
            self.submodules.descrambler = descrambler = Descrambler()

        # dataflow
        self.comb += [
            sink.connect(converter.sink),
            converter.source.connect(bitslip.sink),
            bitslip.source.connect(decoder.sink)
        ]
        if with_scrambling:
            self.comb += [
                decoder.source.connect(descrambler.sink),
                descrambler.source.connect(source)
            ]
        else:
            self.comb += [
                decoder.source.connect(source, omit={"d", "k"}),
                source.data.eq(decoder.source.d)
            ]

        # idle decoding
        idle_timer = WaitTimer(32)
        self.submodules += idle_timer
        self.sync += [
            If(converter.source.stb,
                idle_timer.wait.eq((converter.source.data == 0) | (converter.source.data == (2**40-1)))
            ),
            idle.eq(idle_timer.done)
        ]
        # comma decoding
        self.sync += \
            If(decoder.source.stb,
                comma.eq((decoder.source.k == 1) & (decoder.source.d == K(28, 5)))
            )
