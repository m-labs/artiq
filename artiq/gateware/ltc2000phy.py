# I/O block for LTC2000 DAC

from migen import *
from migen.genlib.cdc import MultiReg
from misoc.interconnect.csr import *

class Ltc2000phy(Module, AutoCSR):
    def __init__(self, pads, clk_freq=125e6):
        self.data = Signal(16*24) # 16 bits per channel, 24 phases input at sys clock rate
        self.reset = Signal()

        ###

        # 16 bits per channel, 2 channels, 6 samples per clock cycle, data coming in at sys2x rate
        # for 100 MHz sysclk we get 200 MHz * 2 * 6 = 2.4 Gbps
        data_in = Signal(16*2*6) 
        counter = Signal()

        data_2x = Signal.like(self.data)
        self.specials += MultiReg(self.data, data_2x, "sys2x")

        # Load data into register, swapping halves
        self.sync.sys2x += [
            If(~counter,
                data_in.eq(data_2x[16*2*6:])  # Load second half first
            ).Else(
                data_in.eq(data_2x[:16*2*6])  # Load first half second
            ),
            counter.eq(~counter)
        ]

        dac_clk_se = Signal()
        dac_data_se = Signal(16)
        dac_datb_se = Signal(16)

        # sys6x is beyond the reach of OSERDES on EFC at 125MHz
        serdes_clk = ClockSignal("sys6x") if clk_freq == 100e6 else ClockSignal("sys5x")

        self.specials += [
            Instance("OSERDESE2",
                p_DATA_WIDTH=6, p_TRISTATE_WIDTH=1,
                p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                p_SERDES_MODE="MASTER",

                o_OQ=dac_clk_se,
                i_OCE=1,
                i_RST=self.reset,
                i_CLK=serdes_clk, i_CLKDIV=ClockSignal("sys2x"),
                i_D1=0, i_D2=1, i_D3=0, i_D4=1,
                i_D5=0, i_D6=1
            ),
            Instance("OBUFDS",
                i_I=dac_clk_se,
                o_O=pads.dcki_p,
                o_OB=pads.dcki_n
            )
        ]

        for i in range(16):
            self.specials += [
                Instance("OSERDESE2",
                    p_DATA_WIDTH=6, p_TRISTATE_WIDTH=1,
                    p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                    p_SERDES_MODE="MASTER",

                    o_OQ=dac_data_se[i],
                    i_OCE=1,
                    i_RST=self.reset,
                    i_CLK=serdes_clk, i_CLKDIV=ClockSignal("sys2x"),
                    i_D1=data_in[0*16 + i], i_D2=data_in[2*16 + i],
                    i_D3=data_in[4*16 + i], i_D4=data_in[6*16 + i],
                    i_D5=data_in[8*16 + i], i_D6=data_in[10*16 + i]
                ),
                Instance("OBUFDS",
                    i_I=dac_data_se[i],
                    o_O=pads.data_p[i],
                    o_OB=pads.data_n[i]
                ),
                Instance("OSERDESE2",
                    p_DATA_WIDTH=6, p_TRISTATE_WIDTH=1,
                    p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                    p_SERDES_MODE="MASTER",

                    o_OQ=dac_datb_se[i],
                    i_OCE=1,
                    i_RST=self.reset,
                    i_CLK=serdes_clk, i_CLKDIV=ClockSignal("sys2x"),
                    i_D1=data_in[1*16 + i], i_D2=data_in[3*16 + i],
                    i_D3=data_in[5*16 + i], i_D4=data_in[7*16 + i],
                    i_D5=data_in[9*16 + i], i_D6=data_in[11*16 + i]
                ),
                Instance("OBUFDS",
                    i_I=dac_datb_se[i],
                    o_O=pads.datb_p[i],
                    o_OB=pads.datb_n[i]
                )
        ]
