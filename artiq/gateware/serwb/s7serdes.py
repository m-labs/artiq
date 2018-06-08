from migen import *
from migen.genlib.io import *
from migen.genlib.misc import BitSlip, WaitTimer

from misoc.interconnect import stream
from misoc.cores.code_8b10b import Encoder, Decoder

from artiq.gateware.serwb.datapath import TXDatapath, RXDatapath


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
        self.sink = sink = stream.Endpoint([("data", 32)])

        # # #

        # Datapath
        self.submodules.datapath = datapath = TXDatapath(8)
        self.comb += [
            sink.connect(datapath.sink),
            datapath.source.ack.eq(1),
            datapath.idle.eq(idle),
            datapath.comma.eq(comma)
        ]

        # Output  Data(DDR with sys4x)
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
                i_D1=datapath.source.data[0], i_D2=datapath.source.data[1],
                i_D3=datapath.source.data[2], i_D4=datapath.source.data[3],
                i_D5=datapath.source.data[4], i_D6=datapath.source.data[5],
                i_D7=datapath.source.data[6], i_D8=datapath.source.data[7]
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
        self.source = source = stream.Endpoint([("data", 32)])

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

        # Datapath
        self.submodules.datapath = datapath = RXDatapath(8)
        self.comb += [
            datapath.sink.stb.eq(1),
            datapath.sink.data.eq(data_deserialized),
            datapath.bitslip_value.eq(bitslip_value),
            datapath.source.connect(source),
            idle.eq(datapath.idle),
            comma.eq(datapath.comma)
        ]


@ResetInserter()
class S7Serdes(Module):
    def __init__(self, pads, mode="master"):
        self.submodules.clocking = _S7SerdesClocking(pads, mode)
        self.submodules.tx = _S7SerdesTX(pads, mode)
        self.submodules.rx = _S7SerdesRX(pads, mode)
