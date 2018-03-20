from migen import *

from artiq.gateware.rtio.phy import ttl_serdes_generic


# SERDES clocks are in dedicated domains to make the implementation
# of the convoluted clocking schemes from AR#67885 less tedious.


class _OSERDESE2_8X(Module):
    def __init__(self, pad, pad_n=None):
        self.o = Signal(8)
        self.t_in = Signal()
        self.t_out = Signal()

        # # #

        pad_o = Signal()
        self.specials += Instance("OSERDESE3",
            p_DATA_WIDTH=8, p_INIT=0,
            p_IS_CLK_INVERTED=0, p_IS_CLKDIV_INVERTED=0, p_IS_RST_INVERTED=0,

            o_OQ=pad_o, o_T_OUT=self.t_out,
            i_RST=ResetSignal("rtio_serdes"),
            i_CLK=ClockSignal("rtiox4_serdes"), i_CLKDIV=ClockSignal("rtio_serdes"),
            i_D=self.o, i_T=self.t_in)
        if pad_n is None:
            self.comb += pad.eq(pad_o)
        else:
            self.specials += Instance("IOBUFDS_INTERMDISABLE",
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
        self.specials += Instance("ISERDESE3",
            p_IS_CLK_INVERTED=0,
            p_IS_CLK_B_INVERTED=1,
            p_DATA_WIDTH=8,

            i_D=pad_i,
            i_RST=ResetSignal("rtio_serdes"),
            i_FIFO_RD_EN=0,
            i_CLK=ClockSignal("rtiox4_serdes"),
            i_CLK_B=ClockSignal("rtiox4_serdes"), # locally inverted
            i_CLKDIV=ClockSignal("rtio_serdes"),
            o_Q=Cat(*self.i[::-1]))
        if pad_n is None:
            self.comb += pad_i.eq(pad)
        else:
            self.specials += Instance("IBUFDS_INTERMDISABLE",
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
    def __init__(self, pad, pad_n=None):
        serdes = _OSERDESE2_8X(pad, pad_n)
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
