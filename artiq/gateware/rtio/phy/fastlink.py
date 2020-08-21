from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialOutput, DifferentialInput, DDROutput
from misoc.cores.liteeth_mini.mac.crc import LiteEthMACCRCEngine

from artiq.gateware.rtio import rtlink


class SerDes(Module):
    # crc-12 telco: 0x80f
    def __init__(self, n_data=8, t_clk=7, d_clk=0b1100011,
                 n_frame=14, n_crc=12, poly=0x80f):
        """DDR fast link.

        * One word clock lane with `t_clk` period.
        * Multiple data lanes at DDR speed.
        * One return data lane at slower speed.
        * n_frame//2 - 1 marker bits are used to provide framing.

        * `n_frame` words per frame
        * `t_clk` bits per clk cycle with pattern `d_clk`
        * `n_crc` CRC bits per frame
        """
        # pins
        self.data = [Signal(2) for _ in range(n_data)]
        n_lanes = n_data - 2  # number of data lanes
        n_word = n_lanes*t_clk
        t_frame = t_clk*n_frame//2
        n_body = n_word*n_frame - (n_frame//2 + 1) - n_crc
        t_miso = 0  # miso sampling latency  TODO

        # frame data
        self.payload = Signal(n_body)
        # readback data
        self.readback = Signal(n_frame, reset_less=True)
        # data load synchronization event
        self.stb = Signal()

        # # #

        self.submodules.crc = LiteEthMACCRCEngine(
            data_width=2*n_lanes, width=n_crc, polynom=poly)

        words_ = []
        j = 0
        # last, LSB to first, MSB
        for i in range(n_frame):  # iterate over words
            if i == 0:  # data and checksum
                k = n_word - n_crc
            elif i == 1:  # marker
                words_.append(C(1))
                k = n_word - 1
            elif i < n_frame//2 + 2:  # marker
                words_.append(C(0))
                k = n_word - 1
            else:  # full word
                k = n_word
            # append corresponding frame body bits
            words_.append(self.payload[j:j + k])
            j += k
        words_ = Cat(words_)
        assert len(words_) == n_frame*n_word - n_crc
        words = Signal(len(words_))
        self.comb += words.eq(words_)

        clk = Signal(t_clk, reset=d_clk)
        i = Signal(max=t_frame)
        # big shift register for clk and mosi
        sr = [Signal(t_frame*2 - n_crc//n_lanes, reset_less=True)
              for i in range(n_lanes)]
        assert len(Cat(sr)) == len(words)
        # DDR bits for each register
        ddr_data = Cat([sri[-2] for sri in sr], [sri[-1] for sri in sr])
        self.comb += [
            self.stb.eq(i == t_frame - 1),
            # LiteETHMACCRCEngine takes data LSB first
            self.crc.data[::-1].eq(ddr_data),
        ]
        miso = Signal()
        miso_sr = Signal(t_frame, reset_less=True)
        self.sync.rio_phy += [
            # shift everything by two bits
            clk.eq(Cat(clk[-2:], clk)),
            [sri[2:].eq(sri) for sri in sr],
            self.crc.last.eq(self.crc.next),
            miso_sr.eq(Cat(miso, miso_sr)),
            i.eq(i + 1),
            If(self.stb,
                i.eq(0),
                clk.eq(clk.reset),
                self.crc.last.eq(0),
                # transpose, load
                Cat(sr).eq(Cat(words[mm::n_lanes] for mm in range(n_lanes))),
                self.readback.eq(Cat([miso_sr[int(round(t_miso + i*t_clk/2.))]
                    for i in range(n_frame)])),
            ),
            If(i == t_frame - 2,
                # inject crc for the last cycle
                ddr_data.eq(self.crc.next),
            ),
        ]

        self.comb += [
            self.data[0].eq(clk[-2:]),
            [di.eq(sri[-2:]) for di, sri in zip(self.data[1:-1], sr)],
            miso.eq(self.data[-1]),
        ]


class SerInterface(Module):
    def __init__(self, pins, pins_n):
        n_data = 1 + len(pins.mosi) + 1
        self.data = [Signal(2) for _ in range(n_data)]
        clk_ddr = Signal()
        miso_reg = Signal()
        self.specials += [
            DDROutput(self.data[0][-1], self.data[0][-2],
                clk_ddr, ClockSignal("rio_phy")),
            DifferentialOutput(clk_ddr, pins.clk, pins_n.clk),
            DifferentialInput(pins.miso, pins_n.miso, miso_reg),
            MultiReg(miso_reg, self.data[-1], "rio_phy"),
        ]
        for i in range(len(pins.mosi)):
            ddr = Signal()
            self.specials += [
                DDROutput(self.data[-1], self.data[-2], ddr, ClockSignal("rio_phy")),
                DifferentialOutput(ddr, pins.mosi[i], pins_n.mosi[i]),
            ]
