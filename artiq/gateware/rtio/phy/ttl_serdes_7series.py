from migen.fhdl.std import *

from artiq.gateware.rtio.phy import ttl_serdes_generic


class _OSERDESE2_8X(Module):
    def __init__(self, pad):
        self.o = Signal(8)
        self.t_in = Signal()
        self.t_out = Signal()

        # # #

        o = self.o
        self.specials += Instance("OSERDESE2",
                                  p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                                  p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                                  o_OQ=pad, o_TQ=self.t_out,
                                  i_CLK=ClockSignal("rtiox4"),
                                  i_CLKDIV=ClockSignal("rio_phy"),
                                  i_D1=o[0], i_D2=o[1], i_D3=o[2], i_D4=o[3],
                                  i_D5=o[4], i_D6=o[5], i_D7=o[6], i_D8=o[7],
                                  i_TCE=1, i_OCE=1, i_RST=0,
                                  i_T1=self.t_in)


class _IOSERDESE2_8X(Module):
    def __init__(self, pad):
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()

        # # #

        pad_i = Signal()
        pad_o = Signal()
        i = self.i
        self.specials += Instance("ISERDESE2", p_DATA_RATE="DDR",
                                  p_DATA_WIDTH=8,
                                  p_INTERFACE_TYPE="NETWORKING", p_NUM_CE=1,
                                  o_Q1=i[7], o_Q2=i[6], o_Q3=i[5], o_Q4=i[4],
                                  o_Q5=i[3], o_Q6=i[2], o_Q7=i[1], o_Q8=i[0],
                                  i_D=pad_i,
                                  i_CLK=ClockSignal("rtiox4"),
                                  i_CLKB=~ClockSignal("rtiox4"),
                                  i_CE1=1, i_RST=0,
                                  i_CLKDIV=ClockSignal("rio_phy"))
        oserdes = _OSERDESE2_8X(pad_o)
        self.submodules += oserdes
        self.specials += Instance("IOBUF",
                                  i_I=pad_o, o_O=pad_i, i_T=oserdes.t_out,
                                  io_IO=pad)
        self.comb += [
            oserdes.t_in.eq(~self.oe),
            oserdes.o.eq(self.o)
        ]


class Output_8X(ttl_serdes_generic.Output):
    def __init__(self, pad):
        serdes = _OSERDESE2_8X(pad)
        self.submodules += serdes
        ttl_serdes_generic.Output.__init__(self, serdes)


class Inout_8X(ttl_serdes_generic.Inout):
    def __init__(self, pad):
        serdes = _IOSERDESE2_8X(pad)
        self.submodules += serdes
        ttl_serdes_generic.Inout.__init__(self, serdes)
