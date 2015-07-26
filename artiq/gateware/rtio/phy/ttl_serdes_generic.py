from migen.fhdl.std import *
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
        serdes_width = flen(serdes_o)
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
            rtlink.OInterface(1, fine_ts_width=log2_int(flen(serdes.o))))
        self.probes = [serdes.o[-1]]
        override_en = Signal()
        override_o = Signal()
        self.overrides = [override_en, override_o]

        # # #

        self.submodules += _SerdesDriver(
            serdes.o,
            self.rtlink.o.stb, self.rtlink.o.data, self.rtlink.o.fine_ts,
            override_en, override_o)


class Inout(Module):
    def __init__(self, serdes):
        serdes_width = flen(serdes.o)
        assert flen(serdes.i) == serdes_width
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(2, 2, fine_ts_width=log2_int(serdes_width)),
            rtlink.IInterface(1, fine_ts_width=log2_int(serdes_width)))
        self.probes = [serdes.i[-1], serdes.oe]
        override_en = Signal()
        override_o = Signal()
        override_oe = Signal()
        self.overrides = [override_en, override_o, override_oe]

        # # #

        # Output
        self.submodules += _SerdesDriver(
            serdes_o=serdes.o,
            stb=self.rtlink.o.stb & (self.rtlink.o.address == 0),
            data=self.rtlink.o.data[0],
            fine_ts=self.rtlink.o.fine_ts,
            override_en=override_en, override_o=override_o)

        oe_k = Signal()
        self.sync.rio_phy += [
            If(self.rtlink.o.stb & (self.rtlink.o.address == 1),
                oe_k.eq(self.rtlink.o.data[0])),
            If(override_en,
                serdes.oe.eq(override_oe)
            ).Else(
                serdes.oe.eq(oe_k)
            )
        ]

        # Input
        sensitivity = Signal(2)
        self.sync.rio += If(self.rtlink.o.stb & (self.rtlink.o.address == 2),
            sensitivity.eq(self.rtlink.o.data))

        i = serdes.i[-1]
        i_d = Signal()
        self.sync.rio_phy += [
            i_d.eq(i),
            self.rtlink.i.stb.eq(
                (sensitivity[0] & ( i & ~i_d)) |
                (sensitivity[1] & (~i &  i_d))
            ),
            self.rtlink.i.data.eq(i),
        ]

        pe = PriorityEncoder(serdes_width)
        self.submodules += pe
        self.comb += pe.i.eq(serdes.i ^ Replicate(i_d, serdes_width))
        self.sync.rio_phy += self.rtlink.i.fine_ts.eq(pe.o)


class _FakeSerdes(Module):
    def __init__(self):
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()


class _OutputTB(Module):
    def __init__(self):
        serdes = _FakeSerdes()
        self.submodules.dut = RenameClockDomains(Output(serdes),
                                                 {"rio_phy": "sys"})

    def gen_simulation(self, selfp):
        selfp.dut.rtlink.o.data = 1
        selfp.dut.rtlink.o.fine_ts = 1
        selfp.dut.rtlink.o.stb = 1
        yield
        selfp.dut.rtlink.o.stb = 0
        yield
        selfp.dut.rtlink.o.data = 0
        selfp.dut.rtlink.o.fine_ts = 2
        selfp.dut.rtlink.o.stb = 1
        yield
        yield
        selfp.dut.rtlink.o.data = 1
        selfp.dut.rtlink.o.fine_ts = 7
        selfp.dut.rtlink.o.stb = 1
        for _ in range(6):
            # note that stb stays active; output should not change
            yield


class _InoutTB(Module):
    def __init__(self):
        self.serdes = _FakeSerdes()
        self.submodules.dut = RenameClockDomains(Inout(self.serdes),
                                                 {"rio_phy": "sys",
                                                  "rio": "sys"})

    def check_input(self, selfp, stb, fine_ts=None):
        if stb != selfp.dut.rtlink.i.stb:
            print("KO rtlink.i.stb should be {} but is {}"
                  .format(stb, selfp.dut.rtlink.i.stb))
        elif fine_ts is not None and fine_ts != selfp.dut.rtlink.i.fine_ts:
            print("KO rtlink.i.fine_ts should be {} but is {}"
                  .format(fine_ts, selfp.dut.rtlink.i.fine_ts))
        else:
            print("OK")

    def check_output(self, selfp, data):
        if selfp.serdes.o != data:
            print("KO io.o should be {} but is {}".format(data, selfp.serdes.o))
        else:
            print("OK")

    def check_output_enable(self, selfp, oe):
        if selfp.serdes.oe != oe:
            print("KO io.oe should be {} but is {}".format(oe, selfp.serdes.oe))
        else:
            print("OK")

    def gen_simulation(self, selfp):
        selfp.dut.rtlink.o.address = 2
        selfp.dut.rtlink.o.data = 0b11
        selfp.dut.rtlink.o.stb = 1  # set sensitivity to rising + falling
        yield
        selfp.dut.rtlink.o.stb = 0

        self.check_output_enable(selfp, 0)
        yield

        selfp.serdes.i = 0b11111110  # rising edge at fine_ts = 1
        yield
        selfp.serdes.i = 0b11111111
        yield
        self.check_input(selfp, stb=1, fine_ts=1)

        selfp.serdes.i = 0b01111111  # falling edge at fine_ts = 7
        yield
        selfp.serdes.i = 0b00000000
        yield
        self.check_input(selfp, stb=1, fine_ts=7)

        selfp.serdes.i = 0b11000000  # rising edge at fine_ts = 6
        yield
        selfp.serdes.i = 0b11111111
        yield
        self.check_input(selfp, stb=1, fine_ts=6)

        selfp.dut.rtlink.o.address = 2
        selfp.dut.rtlink.o.data = 0b11
        selfp.dut.rtlink.o.stb = 1  # set sensitivity to rising only
        yield
        selfp.dut.rtlink.o.stb = 0
        yield

        selfp.serdes.i = 0b00001111  # falling edge at fine_ts = 4
        yield
        self.check_input(selfp, stb=0)  # no strobe, sensitivity is rising edge

        selfp.serdes.i = 0b11110000  # rising edge at fine_ts = 4
        yield
        self.check_input(selfp, stb=1, fine_ts=4)

        selfp.dut.rtlink.o.address = 1
        selfp.dut.rtlink.o.data = 1
        selfp.dut.rtlink.o.stb = 1  # set Output Enable to 1
        yield
        selfp.dut.rtlink.o.stb = 0
        yield
        yield
        self.check_output_enable(selfp, 1)

        selfp.dut.rtlink.o.address = 0
        selfp.dut.rtlink.o.data = 1
        selfp.dut.rtlink.o.fine_ts = 3
        selfp.dut.rtlink.o.stb = 1  # rising edge at fine_ts = 3
        yield
        selfp.dut.rtlink.o.stb = 0
        yield
        self.check_output(selfp, data=0b11111000)

        yield
        self.check_output(selfp, data=0xFF)  # stays at 1
        
        selfp.dut.rtlink.o.data = 0
        selfp.dut.rtlink.o.fine_ts = 0
        selfp.dut.rtlink.o.stb = 1  # falling edge at fine_ts = 0
        yield
        selfp.dut.rtlink.o.stb = 0
        yield
        self.check_output(selfp, data=0)

        yield
        self.check_output(selfp, data=0)
        
        selfp.dut.rtlink.o.data = 1
        selfp.dut.rtlink.o.fine_ts = 7
        selfp.dut.rtlink.o.stb = 1  # rising edge at fine_ts = 7
        yield
        selfp.dut.rtlink.o.stb = 0
        yield
        self.check_output(selfp, data=0b10000000)


if __name__ == "__main__":
    import sys
    from migen.sim.generic import Simulator, TopLevel

    if len(sys.argv) != 2:
        print("Incorrect command line")
        sys.exit(1)

    cls = {
        "output": _OutputTB,
        "inout": _InoutTB
    }[sys.argv[1]]

    with Simulator(cls(), TopLevel("top.vcd", clk_period=int(1/0.125))) as s:
        s.run()
