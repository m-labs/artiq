from migen import *
from misoc.cores.duc import MultiDDS

from artiq.gateware.rtio import rtlink
from .fastlink import SerDes, SerInterface


class Phy(Module):
    def __init__(self, regs):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=32, address_width=4,
                              enable_replace=True))
        self.sync.rtio += [
            If(self.rtlink.o.stb,
                Array(regs)[self.rtlink.o.address].eq(self.rtlink.o.data)
            )
        ]


class DDSChannel(Module):
    def __init__(self, share_lut=None):
        to_rio_phy = ClockDomainsRenamer("rio_phy")
        self.submodules.dds = to_rio_phy(MultiDDS(
            n=5, fwidth=32, xwidth=16, z=19, zl=10, share_lut=share_lut))
        self.submodules.frequency = Phy([i.f for i in self.dds.i])
        self.submodules.phase_amplitude = Phy(
            [Cat(i.a, i.clr, i.p) for i in self.dds.i])


class Phaser(Module):
    def __init__(self, pins, pins_n):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=8, address_width=8,
                              enable_replace=False),
            rtlink.IInterface(data_width=10))

        # share a CosSinGen LUT between the two channels
        self.submodules.ch0 = DDSChannel()
        self.submodules.ch1 = DDSChannel(share_lut=self.ch0.dds.cs.lut)
        n_channels = 2
        n_samples = 8
        n_bits = 14
        body = Signal(n_samples*n_channels*2*n_bits, reset_less=True)
        self.sync.rio_phy += [
            If(self.ch0.dds.valid,  # & self.ch1.dds.valid,
                # recent:ch0:i as low order in body
                Cat(body).eq(Cat(self.ch0.dds.o.i[2:], self.ch0.dds.o.q[2:],
                                 self.ch1.dds.o.i[2:], self.ch1.dds.o.q[2:],
                                 body)),
            ),
        ]

        self.submodules.serializer = SerDes(
            n_data=8, t_clk=8, d_clk=0b00001111,
            n_frame=10, n_crc=6, poly=0x2f)
        self.submodules.intf = SerInterface(pins, pins_n)
        self.comb += [
            Cat(self.intf.data[:-1]).eq(Cat(self.serializer.data[:-1])),
            self.serializer.data[-1].eq(self.intf.data[-1]),
        ]

        header = Record([
            ("we", 1),
            ("addr", 7),
            ("data", 8),
            ("type", 4)
        ])
        assert len(Cat(header.raw_bits(), body)) == \
                len(self.serializer.payload)
        self.comb += self.serializer.payload.eq(Cat(header.raw_bits(), body))

        re_dly = Signal(3)  # stage, send, respond
        self.sync.rtio += [
            header.type.eq(1),  # body type is baseband data
            If(self.serializer.stb,
                self.ch0.dds.stb.eq(1),  # synchronize
                self.ch1.dds.stb.eq(1),  # synchronize
                header.we.eq(0),
                re_dly.eq(re_dly[1:]),
            ),
            If(self.rtlink.o.stb,
                re_dly[-1].eq(~self.rtlink.o.address[-1]),
                header.we.eq(self.rtlink.o.address[-1]),
                header.addr.eq(self.rtlink.o.address),
                header.data.eq(self.rtlink.o.data),
            ),
            self.rtlink.i.stb.eq(re_dly[0] & self.serializer.stb),
            self.rtlink.i.data.eq(self.serializer.readback),
        ]
