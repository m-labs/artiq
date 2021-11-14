from migen import *

from artiq.gateware.rtio.phy import ttl_serdes_generic


class _OSERDESE3(Module):
    def __init__(self, dw):
        self.ser_out = Signal()
        self.o = Signal(dw)
        self.t_in = Signal()
        self.t_out = Signal()

        # # #

        pad_o = Signal()
        self.specials += Instance("OSERDESE3",
            p_DATA_WIDTH=dw, p_INIT=0,
            p_IS_CLK_INVERTED=0, p_IS_CLKDIV_INVERTED=0, p_IS_RST_INVERTED=0,

            o_OQ=self.ser_out, o_T_OUT=self.t_out,
            i_RST=ResetSignal("rtio"),
            i_CLK=ClockSignal("rtiox"), i_CLKDIV=ClockSignal("rtio"),
            i_D=self.o, i_T=self.t_in)


class _ISERDESE3(Module):
    def __init__(self, dw):
        self.ser_in = Signal()
        self.o = Signal(dw)
        self.i = Signal(dw)
        self.oe = Signal()

        # # #

        pad_i = Signal()
        self.specials += Instance("ISERDESE3",
            p_IS_CLK_INVERTED=0,
            p_IS_CLK_B_INVERTED=1,
            p_DATA_WIDTH=dw,

            i_D=self.ser_in,
            i_RST=ResetSignal("rtio"),
            i_FIFO_RD_EN=0,
            i_CLK=ClockSignal("rtiox"),
            i_CLK_B=ClockSignal("rtiox"), # locally inverted
            i_CLKDIV=ClockSignal("rtio"),
            o_Q=Cat(*[self.i[i] for i in reversed(range(dw))]))


class _IOSERDESE3(Module):
    def __init__(self, dw):
        self.o = Signal(dw)
        self.i = Signal(dw)
        self.oe = Signal()

        # # #

        iserdes = _ISERDESE3(dw)
        oserdes = _OSERDESE3(dw)
        self.submodules += iserdes, oserdes
        self.comb += [
            self.i.eq(iserdes.i),
            oserdes.t_in.eq(~self.oe),
            oserdes.o.eq(self.o)
        ]
        self.ser_out = oserdes.ser_out
        self.ser_in = iserdes.ser_in
        self.t_out = oserdes.t_out


class Output(ttl_serdes_generic.Output):
    def __init__(self, dw, pad, pad_n=None, dci=False):
        serdes = _OSERDESE3(dw)
        self.submodules += serdes
        ttl_serdes_generic.Output.__init__(self, serdes)

        if pad_n is None:
            self.comb += pad.eq(serdes.ser_out)
        else:
            self.specials += Instance("IOBUFDS",
                i_I=serdes.ser_out,
                i_T=serdes.t_out,
                io_IO=pad, io_IOB=pad_n)


class InOut(ttl_serdes_generic.InOut):
    def __init__(self, dw, pad, pad_n=None, dci=False):
        serdes = _IOSERDESE3(dw)
        self.submodules += serdes
        ttl_serdes_generic.InOut.__init__(self, serdes)

        if pad_n is None:
            self.specials += Instance("IOBUF",
                i_I=serdes.ser_out, o_O=serdes.ser_in, i_T=serdes.t_out,
                io_IO=pad)
        else:
            self.specials += Instance("IOBUFDS_INTERMDISABLE",
                i_IBUFDISABLE=~serdes.t_out,
                i_INTERMDISABLE=~serdes.t_out,
                i_I=serdes.ser_out, o_O=serdes.ser_in, i_T=serdes.t_out,
                io_IO=pad, io_IOB=pad_n)
