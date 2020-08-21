from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialOutput, DifferentialInput, DDROutput
from misoc.cores.liteeth_mini.mac.crc import LiteEthMACCRCEngine

from artiq.gateware.rtio import rtlink


class SerDes(Module):
    # crc-12 telco: 0x80f
    def __init__(self, pins, pins_n, t_clk=7, d_clk=0b1100011,
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
        n_lanes = len(pins.mosi)  # number of data lanes
        n_word = n_lanes*t_clk
        n_body = n_word*n_frame - (n_frame//2 + 1) - n_crc

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
        clk_stb = Signal()
        i_frame = Signal(max=t_clk*n_frame//2)  # DDR
        frame_stb = Signal()
        # big shift register for clk and mosi
        sr = [Signal(n_frame*t_clk - n_crc//n_lanes, reset_less=True)
              for i in range(n_lanes)]
        assert len(Cat(sr)) == len(words)
        # DDR bits for each register
        ddr_data = Cat([sri[-2] for sri in sr], [sri[-1] for sri in sr])
        self.comb += [
            # assert one cycle ahead
            clk_stb.eq(~clk[0] & clk[-1]),
            # double period because of DDR
            frame_stb.eq(i_frame == t_clk*n_frame//2 - 1),

            # LiteETHMACCRCEngine takes data LSB first
            self.crc.data[::-1].eq(ddr_data),
            self.stb.eq(frame_stb & clk_stb),
        ]
        miso = Signal()
        miso_sr = Signal(n_frame, reset_less=True)
        self.sync.rio_phy += [
            # shift clock pattern by two bits each DDR cycle
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
                self.readback.eq(miso_sr),
            ),
            If(i_frame == t_clk*n_frame//2 - 2,
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
