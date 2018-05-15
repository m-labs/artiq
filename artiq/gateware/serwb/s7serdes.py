from migen import *
from migen.genlib.io import *
from migen.genlib.misc import BitSlip, WaitTimer

from misoc.interconnect import stream
from misoc.cores.code_8b10b import Encoder, Decoder


def K(x, y):
    return (y << 5) | x


class _S7SerdesClocking(Module):
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
                Instance("OSERDESE2",
                    p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                    p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                    p_SERDES_MODE="MASTER",

                    o_OQ=self.refclk,
                    i_OCE=1,
                    i_RST=ResetSignal("sys"),
                    i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal("sys"),
                    i_D1=converter.source.data[0], i_D2=converter.source.data[1],
                    i_D3=converter.source.data[2], i_D4=converter.source.data[3],
                    i_D5=converter.source.data[4], i_D6=converter.source.data[5],
                    i_D7=converter.source.data[6], i_D8=converter.source.data[7]
                ),
                DifferentialOutput(self.refclk, pads.clk_p, pads.clk_n)
            ]

        # In Slave mode, multiply the clock provided by Master with a PLL/MMCM
        elif mode == "slave":
            self.specials += DifferentialInput(pads.clk_p, pads.clk_n, self.refclk)


class _S7SerdesTX(Module):
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
            Instance("OSERDESE2",
                p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                p_SERDES_MODE="MASTER",

                o_OQ=data,
                i_OCE=1,
                i_RST=ResetSignal("sys"),
                i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal("sys"),
                i_D1=converter.source.data[0], i_D2=converter.source.data[1],
                i_D3=converter.source.data[2], i_D4=converter.source.data[3],
                i_D5=converter.source.data[4], i_D6=converter.source.data[5],
                i_D7=converter.source.data[6], i_D8=converter.source.data[7]
            ),
            DifferentialOutput(data, pads.tx_p, pads.tx_n)
        ]


class _S7SerdesRX(Module):
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
            Instance("IDELAYE2",
                p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
                p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE",
                p_REFCLK_FREQUENCY=200.0, p_PIPE_SEL="FALSE",
                p_IDELAY_TYPE="VARIABLE", p_IDELAY_VALUE=0,

                i_C=ClockSignal(),
                i_LD=self.delay_rst,
                i_CE=self.delay_inc,
                i_LDPIPEEN=0, i_INC=1,

                i_IDATAIN=data_nodelay, o_DATAOUT=data_delayed
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=8, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=data_delayed,
                i_CE1=1,
                i_RST=ResetSignal("sys"),
                i_CLK=ClockSignal("sys4x"), i_CLKB=~ClockSignal("sys4x"),
                i_CLKDIV=ClockSignal("sys"),
                i_BITSLIP=0,
                o_Q8=data_deserialized[0], o_Q7=data_deserialized[1],
                o_Q6=data_deserialized[2], o_Q5=data_deserialized[3],
                o_Q4=data_deserialized[4], o_Q3=data_deserialized[5],
                o_Q2=data_deserialized[6], o_Q1=data_deserialized[7]
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
class S7Serdes(Module):
    def __init__(self, pads, mode="master"):
        self.submodules.clocking = _S7SerdesClocking(pads, mode)
        self.submodules.tx = _S7SerdesTX(pads, mode)
        self.submodules.rx = _S7SerdesRX(pads, mode)
