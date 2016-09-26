from migen import *


def K(x, y):
    return (y << 5) | x


class LinkLayerTX(Module):
    def __init__(self, encoder):
        nwords = len(encoder.k)
        # nwords must be a power of 2
        assert nwords & (nwords - 1) == 0

        self.link_init = Signal()

        self.aux_frame = Signal()
        self.aux_data = Signal(2*nwords)
        self.aux_ack = Signal()

        self.rt_frame = Signal()
        self.rt_data = Signal(8*nwords)

        self.transceiver_data = Signal(10*nwords)

        # # #

        # Idle and auxiliary traffic use special characters excluding
        # K.28.7 and K.29.7 in order to easily separate the link initialization
        # phase (K.28.7 is additionally excluded as we cannot guarantee its
        # non-repetition here).
        # A set of 8 special characters is chosen using a 3-bit control word.
        # This control word is scrambled to reduce EMI. The control words have
        # the following meanings:
        #   100 idle/auxiliary framing
        #   0AB 2 bits of auxiliary data
        aux_scrambler = Scrambler(3*nwords)
        self.submodules += aux_scrambler
        aux_data_ctl = []
        for i in range(nwords):
            aux_data_ctl.append(self.aux_data[i*2:i*2+1])
            aux_data_ctl.append(0)
        self.comb += [
            If(self.aux_frame,
                aux_scrambler.i.eq(Cat(*aux_data_ctl))
            ).Else(
                aux_scrambler.i.eq(Replicate(0b100, nwords))
            ),
            aux_scrambler.ce.eq(~self.rt_frame),
            self.aux_ack.eq(~self.rt_frame)
        ]
        for i in range(nwords):
            scrambled_ctl = scrambler.o[i*3:i*3+3]
            self.sync += [
                encoder.k[i].eq(1),
                If(scrambled_ctl == 7,
                    encoder.d[i].eq(K(23, 7))
                ).Else(
                    encoder.d[i].eq(K(28, scrambled_ctl))
                )
            ]

        # Real-time traffic uses data characters and is framed by the special
        # characters of auxiliary traffic. RT traffic is also scrambled.
        rt_scrambler = Scrambler(8*nwords)
        self.submodules += rt_scrambler
        self.comb += rt_scrambler.i.eq(self.rt_data)
        rt_frame_r = Signal()
        self.sync += [
            rt_frame_r.eq(self.rt_frame),
            If(rt_frame_r,
                [k.eq(0) for k in encoder.k],
                [d.eq(self.rt_data[i*8:i*8+8]) for i, d in enumerate(encoder.d)]
            )
        ]

        # During link init, send a series of 1*K.28.7 (comma) + 31*K.29.7
        # The receiving end configures its transceiver to also place the comma
        # on its LSB, achieving fixed (or known) latency and alignment of
        # packet starts.
        # K.29.7 is chosen to avoid comma alignment issues arising from K.28.7.
        link_init_r = Signal()
        link_init_counter = Signal(max=32//nwords)
        self.sync += [
            link_init_r.eq(self.link_init),
            If(link_init_r,
                link_init_counter.eq(link_init_counter + 1),
                [k.eq(1) for k in encoder.k],
                [d.eq(K(29, 7)) for d in encoder.d[1:]],
                If(link_init_counter == 0,
                    encoder.d[0].eq(K(28, 7)),
                ).Else(
                    encoder.d[0].eq(K(29, 7)),
                )
            ).Else(
                link_init_counter.eq(0)
            )
        ]
