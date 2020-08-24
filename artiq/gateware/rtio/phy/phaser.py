from migen import *

from artiq.gateware.rtio import rtlink
from .fastlink import SerDes, SerInterface


class Phaser(Module):
    def __init__(self, pins, pins_n):
        self.config = rtlink.Interface(
            rtlink.OInterface(data_width=8, address_width=8,
                enable_replace=False),
            rtlink.IInterface(data_width=10))
        self.data = rtlink.Interface(
            rtlink.OInterface(data_width=32, address_width=8,
                enable_replace=True))

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
        n_channels = 2
        n_samples = 8
        n_bits = 14
        body = [Signal(n_bits) for i in range(n_channels*n_samples*2)]
        assert len(Cat(header.raw_bits(), body)) == \
                len(self.serializer.payload)
        self.comb += self.serializer.payload.eq(Cat(header.raw_bits(), body))

        re_dly = Signal(3)  # stage, send, respond
        self.sync.rtio += [
            header.type.eq(1),  # reserved
            If(self.serializer.stb,
                header.we.eq(0),
                re_dly.eq(re_dly[1:]),
            ),
            If(self.config.o.stb,
                re_dly[-1].eq(~self.config.o.address[-1]),
                header.we.eq(self.config.o.address[-1]),
                header.addr.eq(self.config.o.address),
                header.data.eq(self.config.o.data),
            ),
            self.config.i.stb.eq(re_dly[0] & self.serializer.stb),
            self.config.i.data.eq(self.serializer.readback),
        ]
