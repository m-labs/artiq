from migen import *

from artiq.gateware.rtio.phy import ttl_serdes_generic


class _OSERDESE2_8X(Module):
    def __init__(self, invert=False):
        self.ser_out = Signal()
        self.o = Signal(8)
        self.t_in = Signal()
        self.t_out = Signal()

        # # #

        o = self.o
        self.specials += Instance("OSERDESE2",
            p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
            p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
            p_INIT_OQ=0b11111111 if invert else 0b00000000,
            o_OQ=self.ser_out, o_TQ=self.t_out,
            i_RST=ResetSignal("rio_phy"),
            i_CLK=ClockSignal("rtiox4"),
            i_CLKDIV=ClockSignal("rio_phy"),
            i_D1=o[0] ^ invert, i_D2=o[1] ^ invert, i_D3=o[2] ^ invert, i_D4=o[3] ^ invert,
            i_D5=o[4] ^ invert, i_D6=o[5] ^ invert, i_D7=o[6] ^ invert, i_D8=o[7] ^ invert,
            i_TCE=1, i_OCE=1,
            i_T1=self.t_in)


class _ISERDESE2_8X(Module):
    def __init__(self):
        self.ser_in = Signal()
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()

        # # #

        i = self.i
        self.specials += Instance("ISERDESE2", p_DATA_RATE="DDR",
            p_DATA_WIDTH=8,
            p_INTERFACE_TYPE="NETWORKING", p_NUM_CE=1,
            o_Q1=i[7], o_Q2=i[6], o_Q3=i[5], o_Q4=i[4],
            o_Q5=i[3], o_Q6=i[2], o_Q7=i[1], o_Q8=i[0],
            i_D=self.ser_in,
            i_CLK=ClockSignal("rtiox4"),
            i_CLKB=~ClockSignal("rtiox4"),
            i_CE1=1,
            i_RST=ResetSignal("rio_phy"),
            i_CLKDIV=ClockSignal("rio_phy"))


class _IOSERDESE2_8X(Module):
    def __init__(self):
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()

        # # #

        iserdes = _ISERDESE2_8X()
        oserdes = _OSERDESE2_8X()
        self.submodules += iserdes, oserdes
        self.comb += [
            self.i.eq(iserdes.i),
            oserdes.o.eq(self.o),
            oserdes.t_in.eq(~self.oe),
        ]
        self.ser_out = oserdes.ser_out
        self.ser_in = iserdes.ser_in
        self.t_out = oserdes.t_out


class Output_8X(ttl_serdes_generic.Output):
    def __init__(self, pad, pad_n=None, invert=False, dci=False):
        serdes = _OSERDESE2_8X(invert)
        self.submodules += serdes
        ttl_serdes_generic.Output.__init__(self, serdes)

        if pad_n is None:
            self.comb += pad.eq(serdes.ser_out)
        else:
            self.specials += Instance("IOBUFDS",
                i_I=serdes.ser_out,
                i_T=serdes.t_out,
                io_IO=pad, io_IOB=pad_n)


class InOut_8X(ttl_serdes_generic.InOut):
    def __init__(self, pad, pad_n=None, dci=False):
        serdes = _IOSERDESE2_8X()
        self.submodules += serdes
        ttl_serdes_generic.InOut.__init__(self, serdes)

        if pad_n is None:
            self.specials += Instance("IOBUF",
                i_I=serdes.ser_out, o_O=serdes.ser_in, i_T=serdes.t_out,
                io_IO=pad)
        else:
            if dci:
                self.specials += Instance("IOBUFDS_DCIEN",
                    p_DIFF_TERM="TRUE",
                    p_IBUF_LOW_PWR="TRUE",
                    p_USE_IBUFDISABLE="TRUE",
                    i_IBUFDISABLE=~serdes.t_out,
                    i_DCITERMDISABLE=~serdes.t_out,
                    i_I=serdes.ser_out, o_O=serdes.ser_in, i_T=serdes.t_out,
                    io_IO=pad, io_IOB=pad_n)
            else:
                self.specials += Instance("IOBUFDS_INTERMDISABLE",
                    p_DIFF_TERM="TRUE",
                    p_IBUF_LOW_PWR="TRUE",
                    p_USE_IBUFDISABLE="TRUE",
                    i_IBUFDISABLE=~serdes.t_out,
                    i_INTERMDISABLE=~serdes.t_out,
                    i_I=serdes.ser_out, o_O=serdes.ser_in, i_T=serdes.t_out,
                    io_IO=pad, io_IOB=pad_n)
