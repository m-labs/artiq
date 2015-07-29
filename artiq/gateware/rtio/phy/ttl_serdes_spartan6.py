from migen.fhdl.std import *

from artiq.gateware.rtio.phy import ttl_serdes_generic


class _OSERDES2_8X(Module):
    def __init__(self, pad, stb):
        self.o = Signal(8)
        self.t_in = Signal()
        self.t_out = Signal()

        # # #

        cascade = Signal(4)
        o = self.o
        common = dict(p_DATA_RATE_OQ="SDR", p_DATA_RATE_OT="SDR",
                      p_DATA_WIDTH=8, p_OUTPUT_MODE="SINGLE_ENDED", i_TRAIN=0,
                      i_CLK0=ClockSignal("rtiox8"), i_CLK1=0,
                      i_CLKDIV=ClockSignal("rio_phy"),
                      i_IOCE=stb, i_OCE=1, i_TCE=1, i_RST=0,
                      i_T4=self.t_in, i_T3=self.t_in,
                      i_T2=self.t_in, i_T1=self.t_in)

        self.specials += [
            Instance("OSERDES2", p_SERDES_MODE="MASTER",
                     i_D4=o[7], i_D3=o[6], i_D2=o[5], i_D1=o[4],
                     i_SHIFTIN1=1, i_SHIFTIN2=1,
                     i_SHIFTIN3=cascade[2], i_SHIFTIN4=cascade[3],
                     o_SHIFTOUT1=cascade[0], o_SHIFTOUT2=cascade[1],
                     o_OQ=pad, o_TQ=self.t_out, **common),
            Instance("OSERDES2", p_SERDES_MODE="SLAVE",
                     i_D4=o[3], i_D3=o[2], i_D2=o[1], i_D1=o[0],
                     i_SHIFTIN1=cascade[0], i_SHIFTIN2=cascade[1],
                     i_SHIFTIN3=1, i_SHIFTIN4=1,
                     o_SHIFTOUT3=cascade[2], o_SHIFTOUT4=cascade[3],
                     **common),
        ]


class _IOSERDES2_8X(Module):
    def __init__(self, pad, stb):
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()

        # # #

        pad_i = Signal()
        pad_o = Signal()
        cascade = Signal()
        i = self.i
        common = dict(p_BITSLIP_ENABLE="FALSE", p_DATA_RATE="SDR",
                      p_DATA_WIDTH=8, p_INTERFACE_TYPE="RETIMED",
                      i_BITSLIP=0, i_CE0=1, i_IOCE=stb,
                      i_RST=0, i_CLK0=ClockSignal("rtiox8"), i_CLK1=0,
                      i_CLKDIV=ClockSignal("rio_phy"))
        self.specials += [
            Instance("ISERDES2", p_SERDES_MODE="MASTER",
                     o_Q4=i[7], o_Q3=i[6], o_Q2=i[5], o_Q1=i[4],
                     o_SHIFTOUT=cascade, i_D=pad_i, i_SHIFTIN=0,
                     **common),
            Instance("ISERDES2", p_SERDES_MODE="SLAVE",
                     o_Q4=i[3], o_Q3=i[2], o_Q2=i[1], o_Q1=i[0],
                     i_D=0, i_SHIFTIN=cascade, **common),
        ]

        oserdes = _OSERDES2_8X(pad_o, stb)
        self.submodules += oserdes
        self.specials += Instance("IOBUF",
                                  i_I=pad_o, o_O=pad_i, i_T=oserdes.t_out,
                                  io_IO=pad)
        self.comb += [
            oserdes.t_in.eq(~self.oe),
            oserdes.o.eq(self.o),
        ]


class Output_8X(ttl_serdes_generic.Output):
    def __init__(self, pad, stb):
        serdes = _OSERDES2_8X(pad, stb)
        self.submodules += serdes
        ttl_serdes_generic.Output.__init__(self, serdes)


class Inout_8X(ttl_serdes_generic.Inout):
    def __init__(self, pad, stb):
        serdes = _IOSERDES2_8X(pad, stb)
        self.submodules += serdes
        ttl_serdes_generic.Inout.__init__(self, serdes)


class _OSERDES2_4X(Module):
    def __init__(self, pad, stb):
        self.o = Signal(4)
        self.t_in = Signal()
        self.t_out = Signal()

        # # #

        o = self.o
        self.specials += Instance("OSERDES2", p_SERDES_MODE="NONE",
                                  p_DATA_RATE_OQ="SDR", p_DATA_RATE_OT="SDR",
                                  p_DATA_WIDTH=4, p_OUTPUT_MODE="SINGLE_ENDED",
                                  i_TRAIN=0, i_CLK0=ClockSignal("rtiox4"),
                                  i_CLK1=0, i_CLKDIV=ClockSignal("rio_phy"),
                                  i_IOCE=stb, i_OCE=1, i_TCE=1, i_RST=0,
                                  i_T4=self.t_in, i_T3=self.t_in,
                                  i_T2=self.t_in, i_T1=self.t_in,
                                  i_D4=o[3], i_D3=o[2], i_D2=o[1], i_D1=o[0],
                                  o_OQ=pad, o_TQ=self.t_out)


class _IOSERDES2_4X(Module):
    def __init__(self, pad, stb):
        self.o = Signal(4)
        self.i = Signal(4)
        self.oe = Signal()

        # # #

        pad_i = Signal()
        pad_o = Signal()
        i = self.i
        self.specials += Instance("ISERDES2", p_SERDES_MODE="NONE",
                                  p_BITSLIP_ENABLE="FALSE", p_DATA_RATE="SDR",
                                  p_DATA_WIDTH=4, p_INTERFACE_TYPE="RETIMED",
                                  i_BITSLIP=0, i_CE0=1, i_IOCE=stb,
                                  i_RST=0, i_CLK0=ClockSignal("rtiox4"),
                                  i_CLK1=0, i_CLKDIV=ClockSignal("rio_phy"),
                                  o_Q4=i[3], o_Q3=i[2], o_Q2=i[1], o_Q1=i[0],
                                  i_D=pad_i, i_SHIFTIN=0)
        oserdes = _OSERDES2_4X(pad_o, stb)
        self.submodules += oserdes
        self.specials += Instance("IOBUF",
                                  i_I=pad_o, o_O=pad_i, i_T=oserdes.t_out,
                                  io_IO=pad)
        self.comb += [
            oserdes.t_in.eq(~self.oe),
            oserdes.o.eq(self.o),
        ]


class Output_4X(ttl_serdes_generic.Output):
    def __init__(self, pad, stb):
        serdes = _OSERDES2_4X(pad, stb)
        self.submodules += serdes
        ttl_serdes_generic.Output.__init__(self, serdes)


class Inout_4X(ttl_serdes_generic.Inout):
    def __init__(self, pad, stb):
        serdes = _IOSERDES2_4X(pad, stb)
        self.submodules += serdes
        ttl_serdes_generic.Inout.__init__(self, serdes)
