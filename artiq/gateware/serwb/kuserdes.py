from migen import *
from migen.genlib.io import *
from migen.genlib.misc import BitSlip, WaitTimer

from misoc.interconnect import stream
from misoc.cores.code_8b10b import Encoder, Decoder


def K(x, y):
    return (y << 5) | x


class _KUSerdesClocking(Module):
    def __init__(self, pads, mode="master"):
        self.refclk = Signal()

        # # #

        # In Master mode, generate the linerate/10 clock. Slave will re-multiply it.
        if mode == "master":
            converter = stream.Converter(40, 8)
            self.submodules += converter
            self.comb += [
                converter.sink.stb.eq(1),
                converter.source.ack.eq(1),
                converter.sink.data.eq(Replicate(Signal(10, reset=0b1111100000), 4)),
            ]
            self.specials += [
                Instance("OSERDESE3",
                    p_DATA_WIDTH=8, p_INIT=0,
                    p_IS_CLK_INVERTED=0, p_IS_CLKDIV_INVERTED=0,
                    p_IS_RST_INVERTED=0,

                    o_OQ=self.refclk,
                    i_RST=ResetSignal("sys"),
                    i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal("sys"),
                    i_D=converter.source.data
                ),
                DifferentialOutput(self.refclk, pads.clk_p, pads.clk_n)
            ]

        # In Slave mode, multiply the clock provided by Master with a PLL/MMCM
        elif mode == "slave":
            self.specials += DifferentialInput(pads.clk_p, pads.clk_n, self.refclk)


class _KUSerdesTX(Module):
    def __init__(self, pads, mode="master"):
        # Control
        self.idle = idle = Signal()
        self.comma = comma = Signal()

        # Datapath
        self.ce = ce = Signal()
        self.k = k = Signal(4)
        self.d = d = Signal(32)

        # # #

        # 8b10b encoder
        self.submodules.encoder = encoder = CEInserter()(Encoder(4, True))
        self.comb += encoder.ce.eq(ce)

        # 40 --> 8 converter
        converter = stream.Converter(40, 8)
        self.submodules += converter
        self.comb += [
            converter.sink.stb.eq(1),
            converter.source.ack.eq(1),
            # Enable pipeline when converter accepts the 40 bits
            ce.eq(converter.sink.ack),
            # If not idle, connect encoder to converter
            If(~idle,
                converter.sink.data.eq(Cat(*[encoder.output[i] for i in range(4)]))
            ),
            # If comma, send K28.5
            If(comma,
                encoder.k[0].eq(1),
                encoder.d[0].eq(K(28,5)),
            # Else connect TX to encoder
            ).Else(
                encoder.k[0].eq(k[0]),
                encoder.k[1].eq(k[1]),
                encoder.k[2].eq(k[2]),
                encoder.k[3].eq(k[3]),
                encoder.d[0].eq(d[0:8]),
                encoder.d[1].eq(d[8:16]),
                encoder.d[2].eq(d[16:24]),
                encoder.d[3].eq(d[24:32])
            )
        ]

        # Data output (DDR with sys4x)
        data = Signal()
        self.specials += [
              Instance("OSERDESE3",
                p_DATA_WIDTH=8, p_INIT=0,
                p_IS_CLK_INVERTED=0, p_IS_CLKDIV_INVERTED=0, p_IS_RST_INVERTED=0,

                o_OQ=data,
                i_RST=ResetSignal("sys"),
                i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal("sys"),
                i_D=converter.source.data
            ),
            DifferentialOutput(data, pads.tx_p, pads.tx_n)
        ]


class _KUSerdesRX(Module):
    def __init__(self, pads, mode="master"):
        # Control
        self.delay_rst = Signal()
        self.delay_inc = Signal()
        self.bitslip_value = bitslip_value = Signal(6)

        # Status
        self.idle = idle = Signal()
        self.comma = comma = Signal()

        # Datapath
        self.ce = ce = Signal()
        self.k = k = Signal(4)
        self.d = d = Signal(32)

        # # #

        # Data input (DDR with sys4x)
        data_nodelay = Signal()
        data_delayed = Signal()
        data_deserialized = Signal(8)
        self.specials += [
            DifferentialInput(pads.rx_p, pads.rx_n, data_nodelay),
            Instance("IDELAYE3",
                p_CASCADE="NONE", p_UPDATE_MODE="ASYNC", p_REFCLK_FREQUENCY=200.0,
                p_IS_CLK_INVERTED=0, p_IS_RST_INVERTED=0,
                p_DELAY_FORMAT="COUNT", p_DELAY_SRC="IDATAIN",
                p_DELAY_TYPE="VARIABLE", p_DELAY_VALUE=0,

                i_CLK=ClockSignal("sys"),
                i_RST=self.delay_rst, i_LOAD=0,
                i_INC=1, i_EN_VTC=0,
                i_CE=self.delay_inc,

                i_IDATAIN=data_nodelay, o_DATAOUT=data_delayed
            ),
            Instance("ISERDESE3",
                p_IS_CLK_INVERTED=0,
                p_IS_CLK_B_INVERTED=1,
                p_DATA_WIDTH=8,

                i_D=data_delayed,
                i_RST=ResetSignal("sys"),
                i_FIFO_RD_CLK=0, i_FIFO_RD_EN=0,
                i_CLK=ClockSignal("sys4x"),
                i_CLK_B=ClockSignal("sys4x"), # locally inverted
                i_CLKDIV=ClockSignal("sys"),
                o_Q=data_deserialized
            )
        ]

        # 8 --> 40 converter and bitslip
        converter = stream.Converter(8, 40)
        self.submodules += converter
        bitslip = CEInserter()(BitSlip(40))
        self.submodules += bitslip
        self.comb += [
            converter.sink.stb.eq(1),
            converter.source.ack.eq(1),
            # Enable pipeline when converter outputs the 40 bits
            ce.eq(converter.source.stb),
            # Connect input data to converter
            converter.sink.data.eq(data_deserialized),
            # Connect converter to bitslip
            bitslip.ce.eq(ce),
            bitslip.value.eq(bitslip_value),
            bitslip.i.eq(converter.source.data)
        ]

        # 8b10b decoder
        self.submodules.decoders = decoders = [CEInserter()(Decoder(True)) for _ in range(4)]
        self.comb += [decoders[i].ce.eq(ce) for i in range(4)]
        self.comb += [
            # Connect bitslip to decoder
            decoders[0].input.eq(bitslip.o[0:10]),
            decoders[1].input.eq(bitslip.o[10:20]),
            decoders[2].input.eq(bitslip.o[20:30]),
            decoders[3].input.eq(bitslip.o[30:40]),
            # Connect decoder to output
            self.k.eq(Cat(*[decoders[i].k for i in range(4)])),
            self.d.eq(Cat(*[decoders[i].d for i in range(4)])),
        ]

        # Status
        idle_timer = WaitTimer(256)
        self.submodules += idle_timer
        self.comb += [
            idle_timer.wait.eq(1),
            self.idle.eq(idle_timer.done &
                 ((bitslip.o == 0) | (bitslip.o == (2**40-1)))),
            self.comma.eq(
                (decoders[0].k == 1) & (decoders[0].d == K(28,5)) &
                (decoders[1].k == 0) & (decoders[1].d == 0) &
                (decoders[2].k == 0) & (decoders[2].d == 0) &
                (decoders[3].k == 0) & (decoders[3].d == 0))
        ]


@ResetInserter()
class KUSerdes(Module):
    def __init__(self, pads, mode="master"):
        self.submodules.clocking = _KUSerdesClocking(pads, mode)
        self.submodules.tx = _KUSerdesTX(pads, mode)
        self.submodules.rx = _KUSerdesRX(pads, mode)
