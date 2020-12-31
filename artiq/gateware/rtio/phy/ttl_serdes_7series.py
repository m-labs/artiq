from migen import *

from artiq.gateware.rtio.phy import ttl_serdes_generic


class _OSERDESE2_8X(Module):
    def __init__(self, pad, pad_n=None, invert=False):
        self.o = Signal(8)
        self.t_in = Signal()
        self.t_out = Signal()

        # # #

        o = self.o
        pad_o = Signal()
        self.specials += Instance("OSERDESE2",
            p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
            p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
            p_INIT_OQ=0b11111111 if invert else 0b00000000,
            o_OQ=pad_o, o_TQ=self.t_out,
            i_RST=ResetSignal("rio_phy"),
            i_CLK=ClockSignal("rtiox4"),
            i_CLKDIV=ClockSignal("rio_phy"),
            i_D1=o[0] ^ invert, i_D2=o[1] ^ invert, i_D3=o[2] ^ invert, i_D4=o[3] ^ invert,
            i_D5=o[4] ^ invert, i_D6=o[5] ^ invert, i_D7=o[6] ^ invert, i_D8=o[7] ^ invert,
            i_TCE=1, i_OCE=1,
            i_T1=self.t_in)
        if pad_n is None:
            self.comb += pad.eq(pad_o)
        else:
            self.specials += Instance("IOBUFDS_INTERMDISABLE",
                p_DIFF_TERM="FALSE",
                p_IBUF_LOW_PWR="TRUE",
                p_USE_IBUFDISABLE="TRUE",
                i_IBUFDISABLE=1,
                i_INTERMDISABLE=1,
                i_I=pad_o,
                i_T=self.t_out,
                io_IO=pad, io_IOB=pad_n)


class _ISERDESE2_8X(Module):
    def __init__(self, pad, pad_n=None):
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()

        # # #

        pad_i = Signal()
        i = self.i
        self.specials += Instance("ISERDESE2", p_DATA_RATE="DDR",
            p_DATA_WIDTH=8,
            p_INTERFACE_TYPE="NETWORKING", p_NUM_CE=1,
            o_Q1=i[7], o_Q2=i[6], o_Q3=i[5], o_Q4=i[4],
            o_Q5=i[3], o_Q6=i[2], o_Q7=i[1], o_Q8=i[0],
            i_D=pad_i,
            i_CLK=ClockSignal("rtiox4"),
            i_CLKB=~ClockSignal("rtiox4"),
            i_CE1=1,
            i_RST=ResetSignal("rio_phy"),
            i_CLKDIV=ClockSignal("rio_phy"))
        if pad_n is None:
            self.comb += pad_i.eq(pad)
        else:
            self.specials += Instance("IBUFDS_INTERMDISABLE",
                p_DIFF_TERM="TRUE",
                p_IBUF_LOW_PWR="TRUE",
                p_USE_IBUFDISABLE="TRUE",
                i_IBUFDISABLE=0,
                i_INTERMDISABLE=0,
                o_O=pad_i,
                io_I=pad, io_IB=pad_n)


class _IOSERDESE2_8X(Module):
    def __init__(self, pad, pad_n=None):
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()

        # # #

        pad_i = Signal()
        pad_o = Signal()
        iserdes = _ISERDESE2_8X(pad_i)
        oserdes = _OSERDESE2_8X(pad_o)
        self.submodules += iserdes, oserdes
        if pad_n is None:
            self.specials += Instance("IOBUF",
                i_I=pad_o, o_O=pad_i, i_T=oserdes.t_out,
                io_IO=pad)
        else:
            self.specials += Instance("IOBUFDS_INTERMDISABLE",
                p_DIFF_TERM="TRUE",
                p_IBUF_LOW_PWR="TRUE",
                p_USE_IBUFDISABLE="TRUE",
                i_IBUFDISABLE=~oserdes.t_out,
                i_INTERMDISABLE=~oserdes.t_out,
                i_I=pad_o, o_O=pad_i, i_T=oserdes.t_out,
                io_IO=pad, io_IOB=pad_n)
        self.comb += [
            self.i.eq(iserdes.i),
            oserdes.t_in.eq(~self.oe),
            oserdes.o.eq(self.o)
        ]


class Output_8X(ttl_serdes_generic.Output):
    def __init__(self, pad, pad_n=None, invert=False):
        serdes = _OSERDESE2_8X(pad, pad_n, invert=invert)
        self.submodules += serdes
        ttl_serdes_generic.Output.__init__(self, serdes)


class InOut_8X(ttl_serdes_generic.InOut):
    def __init__(self, pad, pad_n=None):
        serdes = _IOSERDESE2_8X(pad, pad_n)
        self.submodules += serdes
        ttl_serdes_generic.InOut.__init__(self, serdes)


class Input_8X(ttl_serdes_generic.InOut):
    def __init__(self, pad, pad_n=None):
        serdes = _ISERDESE2_8X(pad, pad_n)
        self.submodules += serdes
        ttl_serdes_generic.InOut.__init__(self, serdes)
