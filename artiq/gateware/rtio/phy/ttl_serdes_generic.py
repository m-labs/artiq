from migen import *
from migen.genlib.coding import PriorityEncoder

from artiq.gateware.rtio import rtlink


def _mk_edges(w, direction):
    l = [(1 << i) - 1 for i in range(w)]
    if direction == "rising":
        l = [2**w - 1 ^ x for x in l]
    elif direction == "falling":
        pass
    else:
        raise ValueError
    return l


class _SerdesDriver(Module):
    def __init__(self, serdes_o, stb, data, fine_ts, override_en, override_o):
        previous_data = Signal()
        serdes_width = len(serdes_o)
        edges = Array(_mk_edges(serdes_width, "rising"))
        edges_n = Array(_mk_edges(serdes_width, "falling"))
        self.sync.rio_phy += [
            If(stb, previous_data.eq(data)),
            If(override_en,
                serdes_o.eq(Replicate(override_o, serdes_width))
            ).Else(
                If(stb & ~previous_data & data,
                    serdes_o.eq(edges[fine_ts]),
                ).Elif(stb & previous_data & ~data,
                    serdes_o.eq(edges_n[fine_ts]),
                ).Else(
                    serdes_o.eq(Replicate(previous_data, serdes_width)),
                )
            )
        ]


class Output(Module):
    def __init__(self, serdes):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(1, fine_ts_width=log2_int(len(serdes.o))))
        self.probes = [serdes.o[-1]]
        override_en = Signal()
        override_o = Signal()
        self.overrides = [override_en, override_o]

        # # #

        self.submodules += _SerdesDriver(
            serdes.o,
            self.rtlink.o.stb, self.rtlink.o.data, self.rtlink.o.fine_ts,
            override_en, override_o)


class InOut(Module):
    def __init__(self, serdes):
        serdes_width = len(serdes.o)
        assert len(serdes.i) == serdes_width
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(2, 2, fine_ts_width=log2_int(serdes_width)),
            rtlink.IInterface(1, fine_ts_width=log2_int(serdes_width)))
        self.probes = [serdes.i[-1], serdes.oe]
        override_en = Signal()
        override_o = Signal()
        override_oe = Signal()
        self.overrides = [override_en, override_o, override_oe]

        # Output enable, for interfacing to external buffers.
        self.oe = Signal()
        # LSB of the input state (for edge detection; arbitrary choice, support for
        # short pulses will need a more involved solution).
        self.input_state = Signal()

        # # #

        # Output
        self.submodules += _SerdesDriver(
            serdes_o=serdes.o,
            stb=self.rtlink.o.stb & (self.rtlink.o.address == 0),
            data=self.rtlink.o.data[0],
            fine_ts=self.rtlink.o.fine_ts,
            override_en=override_en, override_o=override_o)

        oe_k = Signal()
        self.oe.attr.add("no_retiming")
        self.sync.rio_phy += [
            If(self.rtlink.o.stb & (self.rtlink.o.address == 1),
                oe_k.eq(self.rtlink.o.data[0])),
            If(override_en,
                self.oe.eq(override_oe)
            ).Else(
                self.oe.eq(oe_k)
            )
        ]
        self.comb += serdes.oe.eq(self.oe)

        # Input
        sensitivity = Signal(2)
        sample = Signal()
        self.sync.rio += [
            sample.eq(0),
            If(self.rtlink.o.stb & self.rtlink.o.address[1],
                sensitivity.eq(self.rtlink.o.data),
                If(self.rtlink.o.address[0], sample.eq(1))
            )
        ]

        i = serdes.i[-1]
        self.comb += self.input_state.eq(i)
        i_d = Signal()
        self.sync.rio_phy += [
            i_d.eq(i),
            self.rtlink.i.stb.eq(
                sample |
                (sensitivity[0] & ( i & ~i_d)) |
                (sensitivity[1] & (~i &  i_d))
            ),
            self.rtlink.i.data.eq(i),
        ]

        pe = PriorityEncoder(serdes_width)
        self.submodules += pe
        self.comb += pe.i.eq(serdes.i ^ Replicate(i_d, serdes_width))
        self.sync.rio_phy += self.rtlink.i.fine_ts.eq(pe.o)
