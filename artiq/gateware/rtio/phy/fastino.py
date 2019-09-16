from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialOutput, DifferentialInput, DDROutput
from misoc.cores.liteeth_mini.mac.crc import LiteEthMACCRCEngine

from artiq.gateware.rtio import rtlink


class SerDes(Module):
    def transpose(self, i, n):
        # i is n,m c-contiguous
        # o is m,n c-contiguous
        m = len(i)//n
        assert n*m == len(i)

    def __init__(self, pins, pins_n):
        n_bits = 16  # bits per dac data word
        n_channels = 32  # channels per fastino
        n_div = 7  # bits per lane and word
        assert n_div == 7
        n_frame = 14  # word per frame
        n_lanes = len(pins.mosi)  # number of data lanes
        n_checksum = 12  # checksum bits
        n_addr = 4  # readback address bits
        n_word = n_lanes*n_div
        n_body = n_word*n_frame - (n_frame//2 + 1) - n_checksum

        # dac data words
        self.dacs = [Signal(n_bits) for i in range(n_channels)]
        # dac update enable
        self.enable = Signal(n_channels)
        # configuration word
        self.cfg = Signal(20)
        # readback data
        self.dat_r = Signal(n_frame//2*(1 << n_addr))
        # data load synchronization event
        self.stb = Signal()

        # # #

        # crc-12 telco
        self.submodules.crc = LiteEthMACCRCEngine(
            data_width=2*n_lanes, width=n_checksum, polynom=0x80f)

        addr = Signal(4)
        body_ = Cat(self.cfg, addr, self.enable, self.dacs)
        assert len(body_) == n_body
        body = Signal(n_body)
        self.comb += body.eq(body_)

        words_ = []
        j = 0
        for i in range(n_frame):  # iterate over words
            if i == 0:  # data and checksum
                k = n_word - n_checksum
            elif i == 1:  # marker
                words_.append(C(1))
                k = n_word - 1
            elif i < n_frame//2 + 2:  # marker
                words_.append(C(0))
                k = n_word - 1
            else:  # full word
                k = n_word
            # append corresponding frame body bits
            words_.append(body[j:j + k])
            j += k
        words_ = Cat(words_)
        assert len(words_) == n_frame*n_word - n_checksum
        words = Signal(len(words_))
        self.comb += words.eq(words_)

        clk = Signal(n_div, reset=0b1100011)
        clk_stb = Signal()
        i_frame = Signal(max=n_div*n_frame//2)  # DDR
        frame_stb = Signal()
        sr = [Signal(n_frame*n_div - n_checksum//n_lanes, reset_less=True)
                for i in range(n_lanes)]
        assert len(Cat(sr)) == len(words)
        # DDR bits for each register
        ddr_data = Cat([sri[-2] for sri in sr], [sri[-1] for sri in sr])
        self.comb += [
            # assert one cycle ahead
            clk_stb.eq(~clk[0] & clk[-1]),
            # double period because of DDR
            frame_stb.eq(i_frame == n_div*n_frame//2 - 1),

            # LiteETHMACCRCEngine takes data LSB first
            self.crc.data[::-1].eq(ddr_data),
            self.stb.eq(frame_stb & clk_stb),
        ]
        miso = Signal()
        miso_sr = Signal(n_frame, reset_less=True)
        self.sync.rio_phy += [
            # shift 7 bit clock pattern by two bits each DDR cycle
            clk.eq(Cat(clk[-2:], clk)),
            [sri[2:].eq(sri) for sri in sr],
            self.crc.last.eq(self.crc.next),
            If(clk[:2] == 0,  # TODO: tweak MISO sampling
                miso_sr.eq(Cat(miso, miso_sr)),
            ),
            If(~frame_stb,
                i_frame.eq(i_frame + 1),
            ),
            If(frame_stb & clk_stb,
                i_frame.eq(0),
                self.crc.last.eq(0),
                # transpose, load
                Cat(sr).eq(Cat(words[mm::n_lanes] for mm in range(n_lanes))),
                Array([self.dat_r[i*n_frame//2:(i + 1)*n_frame//2]
                    for i in range(1 << len(addr))])[addr].eq(miso_sr),
                addr.eq(addr + 1),
            ),
            If(i_frame == n_div*n_frame//2 - 2,
                # inject crc
                ddr_data.eq(self.crc.next),
            ),
        ]

        clk_ddr = Signal()
        miso0 = Signal()
        self.specials += [
            DDROutput(clk[-1], clk[-2], clk_ddr, ClockSignal("rio_phy")),
            DifferentialOutput(clk_ddr, pins.clk, pins_n.clk),
            DifferentialInput(pins.miso, pins_n.miso, miso0),
            MultiReg(miso0, miso, "rio_phy"),
        ]
        for sri, ddr, mp, mn in zip(
                sr, Signal(n_lanes), pins.mosi, pins_n.mosi):
            self.specials += [
                DDROutput(sri[-1], sri[-2], ddr, ClockSignal("rio_phy")),
                DifferentialOutput(ddr, mp, mn),
            ]


class Fastino(Module):
    def __init__(self, pins, pins_n):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=32, address_width=8,
                enable_replace=False),
            rtlink.IInterface(data_width=32))

        self.submodules.serializer = SerDes(pins, pins_n)

        # Support staging DAC data (in `dacs`) by writing to the
        # 32 DAC RTIO addresses, if a channel is not "held" by its
        # bit in `hold` the next frame will contain the update.
        # For the DACs held, the update is triggered by setting the
        # corresponding bit in `update`. Update is self-clearing.
        # This enables atomic DAC updates synchronized to a frame edge.
        #
        # This RTIO layout enables narrow RTIO words (32 bit
        # compared to 512), efficient few-channel updates,
        # least amount of DAC state tracking in kernels,
        # at the cost of more DMA and RTIO data ((n*(32+32+64) vs
        # 32+32*16+64))

        hold = Signal.like(self.serializer.enable)

        # TODO: stb, timestamp
        read_regs = Array([
            self.serializer.dat_r[i*7:(i + 1)*7]
            for i in range(1 << 4)
        ])

        cases = {
            # update
            0x20: self.serializer.enable.eq(self.serializer.enable | self.rtlink.o.data),
            # hold
            0x21: hold.eq(self.rtlink.o.data),
            # cfg
            0x22: self.serializer.cfg[:4].eq(self.rtlink.o.data),
            # leds
            0x23: self.serializer.cfg[4:12].eq(self.rtlink.o.data),
            # reserved
            0x24: self.serializer.cfg[12:].eq(self.rtlink.o.data),
        }
        for i in range(len(self.serializer.dacs)):
            cases[i] = [
                self.serializer.dacs[i].eq(self.rtlink.o.data),
                If(~hold[i],
                    self.serializer.enable[i].eq(1),
                )
            ]

        self.sync.rio_phy += [
            If(self.serializer.stb,
                self.serializer.enable.eq(0),
            ),
            If(self.rtlink.o.stb & ~self.rtlink.o.address[-1],
                Case(self.rtlink.o.address[:-1], cases),
            ),
        ]

        self.sync.rtio += [
            self.rtlink.i.stb.eq(self.rtlink.o.stb &
                self.rtlink.o.address[-1]),
            self.rtlink.i.data.eq(
                read_regs[self.rtlink.o.address[:-1]]),
        ]
