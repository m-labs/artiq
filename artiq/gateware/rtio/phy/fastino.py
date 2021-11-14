from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialOutput, DifferentialInput, DDROutput
from misoc.cores.liteeth_mini.mac.crc import LiteEthMACCRCEngine

from artiq.gateware.rtio import rtlink
from .fastlink import SerDes, SerInterface


class Fastino(Module):
    def __init__(self, pins, pins_n, log2_width=0):
        width = 1 << log2_width
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=max(16*width, 32),
                address_width=8,
                enable_replace=False),
            rtlink.IInterface(data_width=14))

        self.submodules.serializer = SerDes(
            n_data=8, t_clk=7, d_clk=0b1100011,
            n_frame=14, n_crc=12, poly=0x80f)
        self.submodules.intf = SerInterface(pins, pins_n)
        self.comb += [
            Cat(self.intf.data[:-1]).eq(Cat(self.serializer.data[:-1])),
            self.serializer.data[-1].eq(self.intf.data[-1]),
        ]

        # dac data words
        dacs = [Signal(16) for i in range(32)]

        header = Record([
            ("cfg", 4),
            ("leds", 8),
            ("typ", 1),
            ("reserved", 7),
            ("addr", 4),
            ("enable", len(dacs)),
        ])
        assert len(Cat(header.raw_bits(), dacs)) == len(self.serializer.payload)

        # # #

        # Support staging DAC data (in `dacs`) by writing to the
        # DAC RTIO addresses, if a channel is not "held" by its
        # bit in `hold` the next frame will contain the update.
        # For the DACs held, the update is triggered by setting the
        # corresponding bit in `update`. Update is self-clearing.
        # This enables atomic DAC updates synchronized to a frame edge.
        #
        # The `log2_width=0` RTIO layout uses one DAC channel per RTIO address
        # and a dense RTIO address space. The RTIO words are narrow.
        # (32 bit compared to 512) and few-channel updates are efficient.
        # There is the least amount of DAC state tracking in kernels,
        # at the cost of more DMA and RTIO data ((n*(32+32+64) vs
        # 32+32*16+64))
        #
        # Other `log2_width` (up to `log2_width=5) settings pack multiple
        # (in powers of two) DAC channels into one group and
        # into one RTIO write.
        # The RTIO data width increases accordingly. The `log2_width`
        # LSBs of the RTIO address for a DAC channel write must be zero and the
        # address space is sparse.

        hold = Signal.like(header.enable)
        continuous = Signal.like(header.enable)
        cic_config = Signal(16)

        read_regs = Array([Signal.like(self.serializer.readback)
            for _ in range(1 << len(header.addr))])

        cases = {
            # update
            0x20: [
                header.enable.eq(self.rtlink.o.data),
                header.typ.eq(0),
            ],
            # hold
            0x21: hold.eq(self.rtlink.o.data),
            # cfg
            0x22: header.cfg.eq(self.rtlink.o.data),
            # leds
            0x23: header.leds.eq(self.rtlink.o.data),
            # reserved bits
            0x24: header.reserved.eq(self.rtlink.o.data),
            # force continuous DAC updates
            0x25: continuous.eq(self.rtlink.o.data),
            # interpolator configuration stage
            0x26: cic_config.eq(self.rtlink.o.data),
            # interpolator update flags
            0x27: [
                header.enable.eq(self.rtlink.o.data),
                header.typ.eq(1),
            ],
        }
        for i in range(0, len(dacs), width):
            cases[i] = [
                Cat(dacs[i:i + width]).eq(self.rtlink.o.data),
                [If(~hold[i + j] & (header.typ == 0),
                    header.enable[i + j].eq(1),
                ) for j in range(width)]
            ]

        self.comb += [
            If(header.typ == 0,
                self.serializer.payload.eq(Cat(header.raw_bits(), dacs)),
            ).Else(
                self.serializer.payload.eq(Cat(header.raw_bits(), Replicate(cic_config, len(dacs)))),
            ),
        ]

        self.sync.rio_phy += [
            If(self.serializer.stb,
                header.typ.eq(0),
                header.enable.eq(continuous),
                read_regs[header.addr].eq(self.serializer.readback),
                header.addr.eq(header.addr + 1),
            ),
            If(self.rtlink.o.stb,
                Case(self.rtlink.o.address, cases),
            ),
        ]

        self.sync.rtio += [
            self.rtlink.i.stb.eq(self.rtlink.o.stb &
                self.rtlink.o.address[-1]),
            self.rtlink.i.data.eq(
                read_regs[self.rtlink.o.address[:-1]]),
        ]
