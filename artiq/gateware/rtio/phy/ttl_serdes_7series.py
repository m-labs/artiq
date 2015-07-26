from migen.fhdl.std import *
from artiq.gateware.rtio.phy import ttl_serdes_generic


class OSerdese2(Module):
    def __init__(self, pad):
        self.o = o = Signal(8)
        self.oe = oe = Signal()
        self.t = t = Signal()

        self.specials += Instance("OSERDESE2", p_DATA_RATE_OQ="DDR",
                                  p_DATA_RATE_TQ="DDR", p_DATA_WIDTH=8,
                                  p_TRISTATE_WIDTH=1, o_OQ=pad, o_TQ=t,
                                  i_CLK=ClockSignal("rtiox4"),
                                  i_CLKDIV=ClockSignal("rio_phy"),
                                  i_D1=o[0], i_D2=o[1], i_D3=o[2], i_D4=o[3],
                                  i_D5=o[4], i_D6=o[5], i_D7=o[6], i_D8=o[7],
                                  i_TCE=1, i_OCE=1, i_RST=ResetSignal(),
                                  i_T1=~oe)


class IOSerdese2(Module):
    def __init__(self, pad):
        ts = TSTriple()
        self.o = o = Signal(8)
        self.oe = oe = Signal()
        self.i = i = Signal(8)
        self.specials += ts.get_tristate(pad)

        self.specials += Instance("ISERDESE2", p_DATA_RATE="DDR",
                                  p_DATA_WIDTH=8,
                                  p_INTERFACE_TYPE="NETWORKING", p_NUM_CE=1,
                                  o_Q1=i[7], o_Q2=i[6], o_Q3=i[5], o_Q4=i[4],
                                  o_Q5=i[3], o_Q6=i[2], o_Q7=i[1], o_Q8=i[0],
                                  i_D=ts.i, i_CLK=ClockSignal("rtiox4"),
                                  i_CE1=1, i_RST=ResetSignal(),
                                  i_CLKDIV=ClockSignal("rio_phy"))

        oserdes = OSerdese2(ts.o)
        self.submodules += oserdes

        self.comb += [
            ts.oe.eq(~oserdes.t),
            oserdes.o.eq(o),
            oserdes.oe.eq(oe)
        ]


class Output(Module):
    def __init__(self, pad):
        serdes = OSerdese2(pad)
        self.submodules += ttl_serdes_generic.Output(serdes, fine_ts_width=3)


class Inout(Module):
    def __init__(self, pad):
        serdes = IOSerdese2(pad)
        self.submodules += ttl_serdes_generic.InOut(serdes, fine_ts_width=3)
