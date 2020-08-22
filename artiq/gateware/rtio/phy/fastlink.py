from migen import *
from migen.genlib.io import (DifferentialOutput, DifferentialInput,
        DDROutput, DDRInput)
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

        * `n_data` lanes
        * `t_clk` bits per clk cycle with pattern `d_clk`
        * `n_frame` words per frame
        * `n_crc` CRC bits per frame for divisor poly `poly`
        """
        # pins
        self.data = [Signal(2) for _ in range(n_data)]
        n_mosi = n_data - 2  # mosi lanes
        n_word = n_mosi*t_clk  # bits per word
        t_frame = t_clk*n_frame  # frame duration
        n_marker = n_frame//2 + 1
        n_body = n_word*n_frame - n_marker - n_crc
        t_miso = 0  # miso sampling latency  TODO

        # frame data
        self.payload = Signal(n_body)
        # readback data
        self.readback = Signal(n_frame, reset_less=True)
        # data load synchronization event
        self.stb = Signal()

        # # #

        self.submodules.crc = LiteEthMACCRCEngine(
            data_width=2*n_mosi, width=n_crc, polynom=poly)

        words_ = []
        j = 0
        # build from LSB to MSB because MSB first
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
        i = Signal(max=t_frame//2)
        # big shift register for clk and mosi
        sr = [Signal(t_frame - n_crc//n_mosi, reset_less=True)
              for i in range(n_mosi)]
        assert len(Cat(sr)) == len(words)
        # DDR bits for each register
        crc_data = [sri[-2] for sri in sr] + [sri[-1] for sri in sr]
        miso_sr = Signal(t_frame, reset_less=True)
        miso_sr_next = Signal.like(miso_sr)
        self.comb += [
            self.stb.eq(i == t_frame//2 - 1),
            # LiteETHMACCRCEngine takes data LSB first
            self.crc.data.eq(Cat(reversed(crc_data))),
            miso_sr_next.eq(Cat(self.data[-1], miso_sr)),
            [di.eq(sri[-2:]) for di, sri in zip(self.data, [clk] + sr)],
        ]
        self.sync.rio_phy += [
            # shift everything by two bits
            [sri.eq(Cat(sri[-2:], sri)) for sri in [clk] + sr],
            miso_sr.eq(miso_sr_next),
            self.crc.last.eq(self.crc.next),
            i.eq(i + 1),
            If(self.stb,
                i.eq(0),
                clk.eq(clk.reset),
                self.crc.last.eq(0),
                # transpose, load
                [sri.eq(Cat(words[i::n_mosi])) for i, sri in enumerate(sr)],
                # unload miso
                self.readback.eq(Cat([miso_sr_next[t_miso + i*t_clk]
                                      for i in range(n_frame)])),
            ),
            If(i == t_frame//2 - 2,
                # inject crc for the last cycle
                Cat(crc_data).eq(self.crc.next),
            ),
        ]


class SerInterface(Module):
    def __init__(self, pins, pins_n):
        self.data = [Signal(2) for _ in range(2 + len(pins.mosi))]

        for d, pp, pn in zip(self.data,
                             [pins.clk] + list(pins.mosi),
                             [pins_n.clk] + list(pins_n.mosi)):
            ddr = Signal()
            self.specials += [
                DDROutput(d[-1], d[-2], ddr, ClockSignal("rio_phy")),
                DifferentialOutput(ddr, pp, pn),
            ]
        ddr = Signal()
        self.specials += [
            DifferentialInput(pins.miso, pins_n.miso, ddr),
            DDRInput(ddr, self.data[-1][-1], self.data[-1][-2],
                     ClockSignal("rio_phy")),
        ]
