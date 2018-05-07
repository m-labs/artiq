from migen import *
from migen.genlib.misc import BitSlip
from migen.genlib.misc import WaitTimer

from misoc.interconnect import stream
from misoc.cores.code_8b10b import Encoder, Decoder


def K(x, y):
    return (y << 5) | x


@ResetInserter()
class KUSSerdes(Module):
    def __init__(self, pads, mode="master"):
        if mode == "slave":
            self.refclk = Signal()

        self.tx_ce = Signal()
        self.tx_k = Signal(4)
        self.tx_d = Signal(32)

        self.rx_ce = Signal()
        self.rx_k = Signal(4)
        self.rx_d = Signal(32)

        self.tx_idle = Signal()
        self.tx_comma = Signal()
        self.rx_idle = Signal()
        self.rx_comma = Signal()

        self.rx_bitslip_value = Signal(6)
        self.rx_delay_rst = Signal()
        self.rx_delay_inc = Signal()
        self.rx_delay_en_vtc = Signal()

        # # #

        self.submodules.encoder = encoder = CEInserter()(Encoder(4, True))
        self.comb += encoder.ce.eq(self.tx_ce)
        self.submodules.decoders = decoders = [CEInserter()(Decoder(True)) for _ in range(4)]
        self.comb += [decoders[i].ce.eq(self.rx_ce) for i in range(4)]

        # clocking:

        # In master mode:
        # - linerate/10 refclk generated on clk_pads
        # In Slave mode:
        # - linerate/10 refclk provided by clk_pads

        # tx clock (linerate/10)
        if mode == "master":
            clk_converter = stream.Converter(40, 8)
            self.submodules += clk_converter
            self.comb += [
                clk_converter.sink.stb.eq(1),
                clk_converter.sink.data.eq(Replicate(Signal(10, reset=0b1111100000), 4)),
                clk_converter.source.ack.eq(1)
            ]
            clk_o = Signal()
            self.specials += [
                Instance("OSERDESE3",
                    p_DATA_WIDTH=8, p_INIT=0,
                    p_IS_CLK_INVERTED=0, p_IS_CLKDIV_INVERTED=0,
                    p_IS_RST_INVERTED=0,

                    o_OQ=clk_o,
                    i_RST=ResetSignal("sys"),
                    i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal("sys"),
                    i_D=clk_converter.source.data
                ),
                Instance("OBUFDS",
                    i_I=clk_o,
                    o_O=pads.clk_p,
                    o_OB=pads.clk_n
                )
            ]

        # tx datapath
        # tx_data -> encoders -> converter -> serdes
        self.submodules.tx_converter = tx_converter = stream.Converter(40, 8)
        self.comb += [
        	tx_converter.sink.stb.eq(1),
        	self.tx_ce.eq(tx_converter.sink.ack),
        	tx_converter.source.ack.eq(1),
            If(self.tx_idle,
                tx_converter.sink.data.eq(0)
            ).Else(
                tx_converter.sink.data.eq(
                    Cat(*[encoder.output[i] for i in range(4)]))
            ),
            If(self.tx_comma,
                encoder.k[0].eq(1),
                encoder.d[0].eq(K(28,5)),
            ).Else(
                encoder.k[0].eq(self.tx_k[0]),
                encoder.k[1].eq(self.tx_k[1]),
                encoder.k[2].eq(self.tx_k[2]),
                encoder.k[3].eq(self.tx_k[3]),
                encoder.d[0].eq(self.tx_d[0:8]),
                encoder.d[1].eq(self.tx_d[8:16]),
                encoder.d[2].eq(self.tx_d[16:24]),
                encoder.d[3].eq(self.tx_d[24:32])
            )
        ]

        serdes_o = Signal()
        self.specials += [
            Instance("OSERDESE3",
                p_DATA_WIDTH=8, p_INIT=0,
                p_IS_CLK_INVERTED=0, p_IS_CLKDIV_INVERTED=0, p_IS_RST_INVERTED=0,

                o_OQ=serdes_o,
                i_RST=ResetSignal("sys"),
                i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal("sys"),
                i_D=tx_converter.source.data
            ),
            Instance("OBUFDS",
                i_I=serdes_o,
                o_O=pads.tx_p,
                o_OB=pads.tx_n
            )
        ]

        # rx clock
        use_bufr = True
        if mode == "slave":
            clk_i = Signal()
            clk_i_bufg = Signal()
            self.specials += [
                Instance("IBUFDS",
                    i_I=pads.clk_p,
                    i_IB=pads.clk_n,
                    o_O=clk_i
                )
            ]
            if use_bufr:
                clk_i_bufr = Signal()
                self.specials += [
                    Instance("BUFR", i_I=clk_i, o_O=clk_i_bufr),
                    Instance("BUFG", i_I=clk_i_bufr, o_O=clk_i_bufg)
                ]
            else:
                self.specials += Instance("BUFG", i_I=clk_i, o_O=clk_i_bufg)
            self.comb += self.refclk.eq(clk_i_bufg)

        # rx datapath
        # serdes -> converter -> bitslip -> decoders -> rx_data
        self.submodules.rx_converter = rx_converter = stream.Converter(8, 40)
        self.comb += [
            self.rx_ce.eq(rx_converter.source.stb),
            rx_converter.source.ack.eq(1)
        ]
        self.submodules.rx_bitslip = rx_bitslip = CEInserter()(BitSlip(40))
        self.comb += rx_bitslip.ce.eq(self.rx_ce)

        serdes_i_nodelay = Signal()
        self.specials += [
            Instance("IBUFDS_DIFF_OUT",
                i_I=pads.rx_p,
                i_IB=pads.rx_n,
                o_O=serdes_i_nodelay
            )
        ]

        serdes_i_delayed = Signal()
        serdes_q = Signal(8)
        self.specials += [
            Instance("IDELAYE3",
                p_CASCADE="NONE", p_UPDATE_MODE="ASYNC", p_REFCLK_FREQUENCY=200.0,
                p_IS_CLK_INVERTED=0, p_IS_RST_INVERTED=0,
                p_DELAY_FORMAT="COUNT", p_DELAY_SRC="IDATAIN",
                p_DELAY_TYPE="VARIABLE", p_DELAY_VALUE=0,

                i_CLK=ClockSignal("sys"),
                i_RST=self.rx_delay_rst, i_LOAD=0,
                i_INC=1, i_EN_VTC=self.rx_delay_en_vtc,
                i_CE=self.rx_delay_inc,

                i_IDATAIN=serdes_i_nodelay, o_DATAOUT=serdes_i_delayed
            ),
            Instance("ISERDESE3",
                p_IS_CLK_INVERTED=0,
                p_IS_CLK_B_INVERTED=1,
                p_DATA_WIDTH=8,

                i_D=serdes_i_delayed,
                i_RST=ResetSignal("sys"),
                i_FIFO_RD_CLK=0, i_FIFO_RD_EN=0,
                i_CLK=ClockSignal("sys4x"),
                i_CLK_B=ClockSignal("sys4x"), # locally inverted
                i_CLKDIV=ClockSignal("sys"),
                o_Q=serdes_q
            )
        ]

        self.comb += [
            rx_converter.sink.stb.eq(1),
            rx_converter.sink.data.eq(serdes_q),
            rx_bitslip.value.eq(self.rx_bitslip_value),
            rx_bitslip.i.eq(rx_converter.source.data),
            decoders[0].input.eq(rx_bitslip.o[0:10]),
            decoders[1].input.eq(rx_bitslip.o[10:20]),
            decoders[2].input.eq(rx_bitslip.o[20:30]),
            decoders[3].input.eq(rx_bitslip.o[30:40]),
            self.rx_k.eq(Cat(*[decoders[i].k for i in range(4)])),
            self.rx_d.eq(Cat(*[decoders[i].d for i in range(4)])),
            self.rx_comma.eq(
                (decoders[0].k == 1) & (decoders[0].d == K(28,5)) &
                (decoders[1].k == 0) & (decoders[1].d == 0) &
                (decoders[2].k == 0) & (decoders[2].d == 0) &
                (decoders[3].k == 0) & (decoders[3].d == 0))
        ]

        idle_timer = WaitTimer(32)
        self.submodules += idle_timer
        self.comb += idle_timer.wait.eq(1)
        self.sync += self.rx_idle.eq(idle_timer.done & (rx_bitslip.o == 0))
