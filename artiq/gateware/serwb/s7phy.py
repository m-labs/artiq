from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg, Gearbox
from migen.genlib.misc import BitSlip

from misoc.cores.code_8b10b import Encoder, Decoder


class S7Serdes(Module):
    def __init__(self, pll, pads, mode="master"):
        self.tx_k = Signal(4)
        self.tx_d = Signal(32)
        self.rx_k = Signal(4)
        self.rx_d = Signal(32)

        self.tx_idle = Signal()
        self.tx_comma = Signal()
        self.rx_idle = Signal()
        self.rx_comma = Signal()

        self.rx_bitslip_value = Signal(6)
        self.rx_delay_rst = Signal()
        self.rx_delay_inc = Signal()
        self.rx_delay_ce = Signal()

        # # #

        self.submodules.encoder = ClockDomainsRenamer("serwb_serdes")(
            Encoder(4, True))
        self.decoders = [ClockDomainsRenamer("serwb_serdes")(
            Decoder(True)) for _ in range(4)]
        self.submodules += self.decoders

        # clocking:

        # In master mode:
        # - linerate/10 pll refclk provided by user
        # - linerate/10 slave refclk generated on clk_pads
        # In Slave mode:
        # - linerate/10 pll refclk provided by clk_pads
        self.clock_domains.cd_serwb_serdes = ClockDomain()
        self.clock_domains.cd_serwb_serdes_5x = ClockDomain()
        self.clock_domains.cd_serwb_serdes_20x = ClockDomain(reset_less=True)
        self.comb += [
            self.cd_serwb_serdes.clk.eq(pll.serwb_serdes_clk),
            self.cd_serwb_serdes_5x.clk.eq(pll.serwb_serdes_5x_clk),
            self.cd_serwb_serdes_20x.clk.eq(pll.serwb_serdes_20x_clk)
        ]
        self.specials += AsyncResetSynchronizer(self.cd_serwb_serdes, ~pll.lock)
        self.comb += self.cd_serwb_serdes_5x.rst.eq(self.cd_serwb_serdes.rst)

        # control/status cdc
        tx_idle = Signal()
        tx_comma = Signal()
        rx_idle = Signal()
        rx_comma = Signal()
        rx_bitslip_value = Signal(6)
        self.specials += [
            MultiReg(self.tx_idle, tx_idle, "serwb_serdes"),
            MultiReg(self.tx_comma, tx_comma, "serwb_serdes"),
            MultiReg(rx_idle, self.rx_idle, "sys"),
            MultiReg(rx_comma, self.rx_comma, "sys")
        ]
        self.specials += MultiReg(self.rx_bitslip_value, rx_bitslip_value, "serwb_serdes"),

        # tx clock (linerate/10)
        if mode == "master":
            self.submodules.tx_clk_gearbox = Gearbox(40, "serwb_serdes", 8, "serwb_serdes_5x")
            self.comb += self.tx_clk_gearbox.i.eq((0b1111100000 << 30) |
                                                  (0b1111100000 << 20) |
                                                  (0b1111100000 << 10) |
                                                  (0b1111100000 <<  0))
            clk_o = Signal()
            self.specials += [
                Instance("OSERDESE2",
                    p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                    p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                    p_SERDES_MODE="MASTER",

                    o_OQ=clk_o,
                    i_OCE=1,
                    i_RST=ResetSignal("serwb_serdes"),
                    i_CLK=ClockSignal("serwb_serdes_20x"), i_CLKDIV=ClockSignal("serwb_serdes_5x"),
                    i_D1=self.tx_clk_gearbox.o[0], i_D2=self.tx_clk_gearbox.o[1],
                    i_D3=self.tx_clk_gearbox.o[2], i_D4=self.tx_clk_gearbox.o[3],
                    i_D5=self.tx_clk_gearbox.o[4], i_D6=self.tx_clk_gearbox.o[5],
                    i_D7=self.tx_clk_gearbox.o[6], i_D8=self.tx_clk_gearbox.o[7]
                ),
                Instance("OBUFDS",
                    i_I=clk_o,
                    o_O=pads.clk_p,
                    o_OB=pads.clk_n
                )
            ]

        # tx datapath
        # tx_data -> encoders -> gearbox -> serdes
        self.submodules.tx_gearbox = Gearbox(40, "serwb_serdes", 8, "serwb_serdes_5x")
        self.comb += [
            If(tx_comma,
                self.encoder.k[0].eq(1),
                self.encoder.d[0].eq(0xbc)
            ).Else(
                self.encoder.k[0].eq(self.tx_k[0]),
                self.encoder.k[1].eq(self.tx_k[1]),
                self.encoder.k[2].eq(self.tx_k[2]),
                self.encoder.k[3].eq(self.tx_k[3]),
                self.encoder.d[0].eq(self.tx_d[0:8]),
                self.encoder.d[1].eq(self.tx_d[8:16]),
                self.encoder.d[2].eq(self.tx_d[16:24]),
                self.encoder.d[3].eq(self.tx_d[24:32])
            )
        ]
        self.sync.serwb_serdes += \
            If(tx_idle,
                self.tx_gearbox.i.eq(0)
            ).Else(
                self.tx_gearbox.i.eq(Cat(*[self.encoder.output[i] for i in range(4)]))
            )

        serdes_o = Signal()
        self.specials += [
            Instance("OSERDESE2",
                p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                p_SERDES_MODE="MASTER",

                o_OQ=serdes_o,
                i_OCE=1,
                i_RST=ResetSignal("serwb_serdes"),
                i_CLK=ClockSignal("serwb_serdes_20x"), i_CLKDIV=ClockSignal("serwb_serdes_5x"),
                i_D1=self.tx_gearbox.o[0], i_D2=self.tx_gearbox.o[1],
                i_D3=self.tx_gearbox.o[2], i_D4=self.tx_gearbox.o[3],
                i_D5=self.tx_gearbox.o[4], i_D6=self.tx_gearbox.o[5],
                i_D7=self.tx_gearbox.o[6], i_D8=self.tx_gearbox.o[7]
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
            self.comb += pll.refclk.eq(clk_i_bufg)

        # rx datapath
        # serdes -> gearbox -> bitslip -> decoders -> rx_data
        self.submodules.rx_gearbox = Gearbox(8, "serwb_serdes_5x", 40, "serwb_serdes")
        self.submodules.rx_bitslip = ClockDomainsRenamer("serwb_serdes")(BitSlip(40))

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
            Instance("IDELAYE2",
                p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
                p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE",
                p_REFCLK_FREQUENCY=200.0, p_PIPE_SEL="FALSE",
                p_IDELAY_TYPE="VARIABLE", p_IDELAY_VALUE=0,

                i_C=ClockSignal(),
                i_LD=self.rx_delay_rst,
                i_CE=self.rx_delay_ce,
                i_LDPIPEEN=0, i_INC=self.rx_delay_inc,

                i_IDATAIN=serdes_i_nodelay, o_DATAOUT=serdes_i_delayed
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=8, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=serdes_i_delayed,
                i_CE1=1,
                i_RST=ResetSignal("serwb_serdes"),
                i_CLK=ClockSignal("serwb_serdes_20x"), i_CLKB=~ClockSignal("serwb_serdes_20x"),
                i_CLKDIV=ClockSignal("serwb_serdes_5x"),
                i_BITSLIP=0,
                o_Q8=serdes_q[0], o_Q7=serdes_q[1],
                o_Q6=serdes_q[2], o_Q5=serdes_q[3],
                o_Q4=serdes_q[4], o_Q3=serdes_q[5],
                o_Q2=serdes_q[6], o_Q1=serdes_q[7]
            )
        ]

        self.comb += [
            self.rx_gearbox.i.eq(serdes_q),
            self.rx_bitslip.value.eq(rx_bitslip_value),
            self.rx_bitslip.i.eq(self.rx_gearbox.o),
            self.decoders[0].input.eq(self.rx_bitslip.o[0:10]),
            self.decoders[1].input.eq(self.rx_bitslip.o[10:20]),
            self.decoders[2].input.eq(self.rx_bitslip.o[20:30]),
            self.decoders[3].input.eq(self.rx_bitslip.o[30:40]),
            self.rx_k.eq(Cat(*[self.decoders[i].k for i in range(4)])),
            self.rx_d.eq(Cat(*[self.decoders[i].d for i in range(4)])),
            rx_idle.eq(self.rx_bitslip.o == 0),
            rx_comma.eq(((self.decoders[0].d == 0xbc) & (self.decoders[0].k == 1)) &
                        ((self.decoders[1].d == 0x00) & (self.decoders[1].k == 0)) &
                        ((self.decoders[2].d == 0x00) & (self.decoders[2].k == 0)) &
                        ((self.decoders[3].d == 0x00) & (self.decoders[3].k == 0)))

        ]
