from migen import *
from migen.genlib.io import *
from migen.genlib.misc import BitSlip, WaitTimer

from misoc.interconnect import stream
from misoc.cores.code_8b10b import Encoder, Decoder

from artiq.gateware.serwb.datapath import TXDatapath, RXDatapath


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
    def __init__(self, pads):
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
              Instance("OSERDESE3",
                p_DATA_WIDTH=8, p_INIT=0,
                p_IS_CLK_INVERTED=0, p_IS_CLKDIV_INVERTED=0, p_IS_RST_INVERTED=0,

                o_OQ=data,
                i_RST=ResetSignal("sys"),
                i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal("sys"),
                i_D=datapath.source.data
            ),
            DifferentialOutput(data, pads.tx_p, pads.tx_n)
        ]


class _KUSerdesRX(Module):
    def __init__(self, pads):
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
class KUSerdes(Module):
    def __init__(self, pads, mode="master"):
        self.submodules.clocking = _KUSerdesClocking(pads, mode)
        self.submodules.tx = _KUSerdesTX(pads)
        self.submodules.rx = _KUSerdesRX(pads)
