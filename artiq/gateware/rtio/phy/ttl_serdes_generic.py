from migen.fhdl.std import *
from artiq.gateware.rtio import rtlink
from migen.genlib.coding import PriorityEncoder


class Output(Module):
    def __init__(self, serdes, fine_ts_width=0):
        self.rtlink = rtlink.Interface(rtlink.OInterface(1, fine_ts_width=
                                                         fine_ts_width))

        serdes_width = 2**fine_ts_width
        o = Signal()
        previous_o = Signal()
        override_en = Signal()
        override_o = Signal()
        io_o = Signal()
        self.overrides = [override_en, override_o]

        io = serdes
        self.submodules += io

        if fine_ts_width > 0:
            timestamp = Signal(fine_ts_width)

            # dout
            edges = Array([0xff ^ ((1 << i) - 1) for i in range(serdes_width)])
            edge_out = Signal(serdes_width)
            edge_out_n = Signal(serdes_width)
            rise_out = Signal()
            fall_out = Signal()
            self.comb += [
                timestamp.eq(self.rtlink.o.fine_ts),
                edge_out.eq(edges[timestamp]),
                edge_out_n.eq(~edge_out),
                rise_out.eq(~previous_o & o),
                fall_out.eq(previous_o & ~o),
                If(override_en,
                    io.o.eq(override_o)
                ).Else(
                    If(rise_out,
                        io.o.eq(edge_out),
                    ).Elif(fall_out,
                        io.o.eq(edge_out_n),
                    ).Else(
                        io.o.eq(Replicate(o, serdes_width)),
                    )
                )
            ]
        else:
            self.comb += [
                If(override_en,
                    io_o.eq(override_o)
                ).Else(
                    io_o.eq(o)
                )
            ]

        self.comb += [
            io.o.eq(io_o),
        ]

        self.sync.rio_phy += [
            If(self.rtlink.o.stb,
                o.eq(self.rtlink.o.data),
            ),
            previous_o.eq(o),
        ]


class Inout(Module):
    def __init__(self, serdes, fine_ts_width=0):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(2, 2, fine_ts_width=fine_ts_width),
            rtlink.IInterface(1, fine_ts_width=fine_ts_width))
        self.probes = []

        serdes_width = 2**fine_ts_width
        self.io = io = serdes
        self.submodules += io
        io_o = Signal(serdes_width)
        io_i = Signal(serdes_width)
        o = Signal()
        rising = Signal()
        falling = Signal()
        i0 = Signal()
        self.oe = oe = Signal()
        override_en = Signal()
        override_o = Signal()
        override_oe = Signal()
        self.sensitivity = Signal(2)
        self.overrides = [override_en, override_o, override_oe]
        previous_o = Signal()

        if fine_ts_width > 0:

            # Input
            self.submodules.pe = pe = PriorityEncoder(serdes_width)

            self.sync.rio_phy += i0.eq(io_i[-1])

            self.comb += [
                io_i.eq(io.i),
                rising.eq(~i0 & io_i[-1]),
                falling.eq(i0 & ~io_i[-1]),
                pe.i.eq(io_i ^ Replicate(falling, serdes_width)),
                self.rtlink.i.data.eq(io_i[-1]),
                self.rtlink.i.fine_ts.eq(pe.o),
            ]

            # Output
            timestamp = Signal(fine_ts_width)
            edges = Array([0xff ^ ((1 << i) - 1) for i in range(serdes_width)])
            edge_out = Signal(serdes_width)
            edge_out_n = Signal(serdes_width)
            rise_out = Signal()
            fall_out = Signal()

            self.comb += [
                timestamp.eq(self.rtlink.o.fine_ts),
                edge_out.eq(edges[timestamp]),
                edge_out_n.eq(~edge_out),
                rise_out.eq(~previous_o & o),
                fall_out.eq(previous_o & ~o),
                If(override_en,
                   io_o.eq(override_o),
                ).Else(
                    If(rise_out,
                        io_o.eq(edge_out),
                    ).Elif(fall_out,
                        io_o.eq(edge_out_n),
                    ).Else(
                        io_o.eq(Replicate(o, serdes_width)),
                    )
                )
            ]
        else:
            self.comb += [
                io_i.eq(io.i),
                rising.eq(~i0 & io_i),
                falling.eq(i0 & ~io_i),
                If(override_en,
                    io_o.eq(override_o)
                ).Else(
                    io_o.eq(o),
                ),
                self.rtlink.i.data.eq(io_i),
            ]

        self.comb += [
            io.oe.eq(oe),
            io.o.eq(io_o),
            self.rtlink.i.stb.eq(
                (self.sensitivity[0] & rising) |
                (self.sensitivity[1] & falling)
            ),
        ]

        self.sync.rio_phy += [
            If(self.rtlink.o.stb,
                If(self.rtlink.o.address == 0, o.eq(self.rtlink.o.data[0])),
                If(self.rtlink.o.address == 1, oe.eq(self.rtlink.o.data[0])),
            ),
            If(override_en,
               oe.eq(override_oe)
            ),
            previous_o.eq(o),
        ]

        self.sync.rio += [
            If(self.rtlink.o.stb & (self.rtlink.o.address == 2),
                self.sensitivity.eq(self.rtlink.o.data)
            )
        ]

class FakeSerdes(Module):
    def __init__(self):
        self.o = o = Signal(8)
        self.oe = oe = Signal(8)


class FakeIOSerdes(Module):
    def __init__(self):
        self.o = o = Signal(8)
        self.oe = oe = Signal(8)
        self.i = i = Signal(8)


class OutputTB(Module):
    def __init__(self):
        serdes = FakeSerdes()
        self.o = RenameClockDomains(Output(serdes, fine_ts_width=3),
                                    {"rio_phy": "sys"})
        self.submodules += self.o

    def gen_simulation(self, selfp):

        yield
        selfp.o.rtlink.o.data = 1
        selfp.o.rtlink.o.fine_ts = 1
        selfp.o.rtlink.o.stb = 1
        yield
        selfp.o.rtlink.o.stb = 0
        yield
        selfp.o.rtlink.o.data = 0
        selfp.o.rtlink.o.fine_ts = 2
        selfp.o.rtlink.o.stb = 1
        yield
        selfp.o.rtlink.o.data = 1
        selfp.o.rtlink.o.fine_ts = 7
        yield

        while True:
            yield


class InoutTB(Module):
    def __init__(self):
        ioserdes = FakeIOSerdes()
        self.io = RenameClockDomains(Inout(ioserdes, fine_ts_width=3),
                                     {"rio_phy": "sys"})
        self.submodules += self.io

    def check_input(self, selfp, stb, fine_ts=None):
        if stb != selfp.io.rtlink.i.stb:
            print("KO rtlink.i.stb should be {} but is {}"
                  .format(stb, selfp.io.rtlink.i.stb))
        elif fine_ts is not None and fine_ts != selfp.io.rtlink.i.fine_ts:
            print("KO rtlink.i.fine_ts should be {} but is {}"
                  .format(fine_ts, selfp.io.rtlink.i.fine_ts))
        else:
            print("OK")

    def check_output(self, selfp, data):
        if selfp.io.io.o != data:
            print("KO io.o should be {} but is {}".format(data, selfp.io.io.o))
        else:
            print("OK")

    def check_output_enable(self, selfp, oe):
        if selfp.io.io.oe != oe:
            print("KO io.oe should be {} but is {}".format(oe, selfp.io.io.oe))
        else:
            print("OK")

    def gen_simulation(self, selfp):
        selfp.io.sensitivity = 0b11  # rising + falling
        self.check_output_enable(selfp, 0)
        yield
        selfp.io.io.i = 0b11111110  # rising edge at fine_ts = 1
        yield
        self.check_input(selfp, stb=1, fine_ts=1)
        selfp.io.io.i = 0b01111111  # falling edge at fine_ts = 7
        yield
        self.check_input(selfp, stb=1, fine_ts=7)
        selfp.io.io.i = 0b11000000  # rising edge at fine_ts = 6
        yield
        self.check_input(selfp, stb=1, fine_ts=6)
        selfp.io.sensitivity = 0b01  # rising
        selfp.io.io.i = 0b00001111  # falling edge at fine_ts = 4
        yield
        self.check_input(selfp, stb=0)  # no strobe, sensitivity is rising edge
        selfp.io.io.i = 0b11110000  # rising edge at fine_ts = 4
        yield
        self.check_input(selfp, stb=1, fine_ts=4)
        selfp.io.rtlink.o.address = 1
        selfp.io.rtlink.o.data = 1
        selfp.io.rtlink.o.stb = 1  # set Output Enable to 1
        yield
        selfp.io.rtlink.o.address = 0
        selfp.io.rtlink.o.data = 1
        selfp.io.rtlink.o.fine_ts = 3  # rising edge at fine_ts = 3
        yield
        self.check_output_enable(selfp, 1)
        yield
        selfp.io.rtlink.o.data = 0
        selfp.io.rtlink.o.fine_ts = 0  # falling edge at fine_ts = 0
        self.check_output(selfp, data=0b11111000)
        yield
        self.check_output(selfp, data=0xFF)  # stays at 1
        yield
        selfp.io.rtlink.o.data = 1
        selfp.io.rtlink.o.fine_ts = 7
        self.check_output(selfp, data=0)
        yield
        self.check_output(selfp, data=0)
        yield
        self.check_output(selfp, data=0b10000000)
        while True:
            yield


if __name__ == "__main__":
    import sys
    from migen.sim.generic import Simulator, TopLevel
    from migen.sim import icarus

    if len(sys.argv) <= 1:
        print("You should run this script with either InoutTB() or OutputTB() "
              "arg")
        sys.exit(1)

    with Simulator(eval(sys.argv[1]), TopLevel("top.vcd", clk_period=int(1/0.125)),
                   icarus.Runner(keep_files=False,)) as s:
        s.run(200)
