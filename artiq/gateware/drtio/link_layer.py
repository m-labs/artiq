from functools import reduce
from operator import xor, or_

from migen import *
from migen.genlib.fsm import *
from migen.genlib.cdc import MultiReg, BusSynchronizer
from migen.genlib.misc import WaitTimer

from misoc.interconnect.csr import *


class Scrambler(Module):
    def __init__(self, n_io, n_state=23, taps=[17, 22]):
        self.i = Signal(n_io)
        self.o = Signal(n_io)

        # # #

        state = Signal(n_state, reset=1)
        curval = [state[i] for i in range(n_state)]
        for i in reversed(range(n_io)):
            flip = reduce(xor, [curval[tap] for tap in taps])
            self.sync += self.o[i].eq(flip ^ self.i[i])
            curval.insert(0, flip)
            curval.pop()

        self.sync += state.eq(Cat(*curval[:n_state]))


def K(x, y):
    return (y << 5) | x


class LinkLayerTX(Module):
    def __init__(self, encoder):
        nwords = len(encoder.k)
        # nwords must be a power of 2
        assert nwords & (nwords - 1) == 0

        self.link_init = Signal()
        self.signal_rx_ready = Signal()

        self.aux_frame = Signal()
        self.aux_data = Signal(2*nwords)
        self.aux_ack = Signal()

        self.rt_frame = Signal()
        self.rt_data = Signal(8*nwords)

        # # #

        # Idle and auxiliary traffic use special characters excluding K.28.7,
        # K.29.7 and K.30.7 in order to easily separate the link initialization
        # phase (K.28.7 is additionally excluded as we cannot guarantee its
        # non-repetition here).
        # A set of 8 special characters is chosen using a 3-bit control word.
        # This control word is scrambled to reduce EMI. The control words have
        # the following meanings:
        #   100 idle/auxiliary framing
        #   0AB 2 bits of auxiliary data
        aux_scrambler = ResetInserter()(CEInserter()(Scrambler(3*nwords)))
        self.submodules += aux_scrambler
        aux_data_ctl = []
        for i in range(nwords):
            aux_data_ctl.append(self.aux_data[i*2:i*2+2])
            aux_data_ctl.append(0)
        self.comb += [
            If(self.aux_frame,
                aux_scrambler.i.eq(Cat(*aux_data_ctl))
            ).Else(
                aux_scrambler.i.eq(Replicate(0b100, nwords))
            ),
            aux_scrambler.reset.eq(self.link_init),
            aux_scrambler.ce.eq(~self.rt_frame),
            self.aux_ack.eq(~self.rt_frame)
        ]
        for i in range(nwords):
            scrambled_ctl = aux_scrambler.o[i*3:i*3+3]
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
        rt_scrambler = ResetInserter()(CEInserter()(Scrambler(8*nwords)))
        self.submodules += rt_scrambler
        self.comb += [
            rt_scrambler.i.eq(self.rt_data),
            rt_scrambler.reset.eq(self.link_init),
            rt_scrambler.ce.eq(self.rt_frame)
        ]
        rt_frame_r = Signal()
        self.sync += [
            rt_frame_r.eq(self.rt_frame),
            If(rt_frame_r,
                [k.eq(0) for k in encoder.k],
                [d.eq(rt_scrambler.o[i*8:i*8+8]) for i, d in enumerate(encoder.d)]
            )
        ]

        # During link init, send a series of 1*K.28.7 (comma) + 31*K.29.7/K.30.7
        # The receiving end configures its transceiver to also place the comma
        # on its LSB, achieving fixed (or known) latency and alignment of
        # packet starts.
        # K.29.7 and K.30.7 are chosen to avoid comma alignment issues arising
        # from K.28.7.
        # K.30.7 is sent instead of K.29.7 to signal the alignment of the local
        # receiver, thus the remote can end its link initialization pattern.
        link_init_r = Signal()
        link_init_counter = Signal(max=32//nwords)
        self.sync += [
            link_init_r.eq(self.link_init),
            If(link_init_r,
                link_init_counter.eq(link_init_counter + 1),
                [k.eq(1) for k in encoder.k],
                If(self.signal_rx_ready,
                    [d.eq(K(30, 7)) for d in encoder.d[1:]]
                ).Else(
                    [d.eq(K(29, 7)) for d in encoder.d[1:]]
                ),
                If(link_init_counter == 0,
                    encoder.d[0].eq(K(28, 7)),
                ).Else(
                    If(self.signal_rx_ready,
                        encoder.d[0].eq(K(30, 7))
                    ).Else(
                        encoder.d[0].eq(K(29, 7))
                    )
                )
            ).Else(
                link_init_counter.eq(0)
            )
        ]


class LinkLayerRX(Module):
    def __init__(self, decoders):
        nwords = len(decoders)
        # nwords must be a power of 2
        assert nwords & (nwords - 1) == 0

        self.link_init = Signal()
        self.remote_rx_ready = Signal()

        self.aux_stb = Signal()
        self.aux_frame = Signal()
        self.aux_data = Signal(2*nwords)

        self.rt_frame = Signal()
        self.rt_data = Signal(8*nwords)

        # # #

        aux_descrambler = ResetInserter()(CEInserter()(Scrambler(3*nwords)))
        rt_descrambler = ResetInserter()(CEInserter()(Scrambler(8*nwords)))
        self.submodules += aux_descrambler, rt_descrambler
        self.comb += [
            self.aux_frame.eq(~aux_descrambler.o[2]),
            self.aux_data.eq(
                Cat(*[aux_descrambler.o[3*i:3*i+2] for i in range(nwords)])),
            self.rt_data.eq(rt_descrambler.o),
        ]

        aux_stb_d = Signal()
        rt_frame_d = Signal()
        self.sync += [
            self.aux_stb.eq(aux_stb_d),
            self.rt_frame.eq(rt_frame_d)
        ]

        link_init_char = Signal()
        self.comb += [
            link_init_char.eq(
                (decoders[0].d == K(28, 7)) |
                (decoders[0].d == K(29, 7)) |
                (decoders[0].d == K(30, 7))),
            If(decoders[0].k,
                If(link_init_char,
                    aux_descrambler.reset.eq(1),
                    rt_descrambler.reset.eq(1)
                ).Else(
                    aux_stb_d.eq(1)
                ),
                aux_descrambler.ce.eq(1)
            ).Else(
                rt_frame_d.eq(1),
                rt_descrambler.ce.eq(1)
            ),
            aux_descrambler.i.eq(Cat(*[d.d[5:] for d in decoders])),
            rt_descrambler.i.eq(Cat(*[d.d for d in decoders]))
        ]
        self.sync += [
            self.link_init.eq(0),
            If(decoders[0].k,
                If(link_init_char, self.link_init.eq(1)),
                If(decoders[0].d == K(30, 7),
                    self.remote_rx_ready.eq(1)
                ).Elif(decoders[0].d != K(28, 7),
                    self.remote_rx_ready.eq(0)
                ),
                If(decoders[1].d == K(30, 7),
                    self.remote_rx_ready.eq(1)
                ) if len(decoders) > 1 else None
            ).Else(
                self.remote_rx_ready.eq(0)
            )
        ]


class LinkLayer(Module, AutoCSR):
    def __init__(self, encoder, decoders, rx_ready_confirm_cycles):
        self.link_status = CSRStatus(3)

        # control signals, in rtio clock domain
        self.reset = Signal()
        self.ready = Signal()
        # pulsed to reset receiver, rx_ready must immediately go low
        self.rx_reset = Signal()
        # receiver locked including comma alignment
        self.rx_ready = Signal()

        tx = ClockDomainsRenamer("rtio")(LinkLayerTX(encoder))
        rx = ClockDomainsRenamer("rtio_rx")(LinkLayerRX(decoders))
        self.submodules += tx, rx

        # in rtio clock domain
        self.tx_aux_frame = tx.aux_frame
        self.tx_aux_data = tx.aux_data
        self.tx_aux_ack = tx.aux_ack
        self.tx_rt_frame = tx.rt_frame
        self.tx_rt_data = tx.rt_data

        # in rtio_rx clock domain
        self.rx_aux_stb = rx.aux_stb
        self.rx_aux_frame = Signal()
        self.rx_aux_data = rx.aux_data
        self.rx_rt_frame = Signal()
        self.rx_rt_data = rx.rt_data

        ready_r = Signal()
        ready_rx = Signal()
        self.sync.rtio += ready_r.eq(self.ready)
        ready_r.attr.add("no_retiming")
        self.specials += MultiReg(ready_r, ready_rx, "rtio_rx")
        self.comb += [
            self.rx_aux_frame.eq(rx.aux_frame & ready_rx),
            self.rx_rt_frame.eq(rx.rt_frame & ready_rx),
        ]

        # # #

        fsm = ClockDomainsRenamer("rtio")(
            ResetInserter()(FSM(reset_state="RESET_RX")))
        self.submodules += fsm

        self.comb += fsm.reset.eq(self.reset)

        rx_remote_rx_ready = Signal()
        rx_link_init = Signal()
        rx.remote_rx_ready.attr.add("no_retiming")
        rx.link_init.attr.add("no_retiming")
        self.specials += [
            MultiReg(rx.remote_rx_ready, rx_remote_rx_ready, "rtio"),
            MultiReg(rx.link_init, rx_link_init, "rtio")
        ]

        link_status = BusSynchronizer(3, "rtio", "sys")
        self.submodules += link_status
        self.comb += self.link_status.status.eq(link_status.o)

        wait_confirm = ClockDomainsRenamer("rtio")(
            WaitTimer(rx_ready_confirm_cycles))
        self.submodules += wait_confirm
        signal_rx_ready_margin = ClockDomainsRenamer("rtio")(WaitTimer(15))
        self.submodules += signal_rx_ready_margin

        fsm.act("RESET_RX",
            link_status.i.eq(0),
            tx.link_init.eq(1),
            self.rx_reset.eq(1),
            NextState("WAIT_LOCAL_RX_READY")
        )
        fsm.act("WAIT_LOCAL_RX_READY",
            link_status.i.eq(1),
            tx.link_init.eq(1),
            If(self.rx_ready, NextState("CONFIRM_LOCAL_RX_READY"))
        )
        fsm.act("CONFIRM_LOCAL_RX_READY",
            link_status.i.eq(2),
            tx.link_init.eq(1),
            wait_confirm.wait.eq(1),
            If(wait_confirm.done, NextState("WAIT_REMOTE_RX_READY")),
            If(~rx_link_init, NextState("RESET_RX"))
        )
        fsm.act("WAIT_REMOTE_RX_READY",
            link_status.i.eq(3),
            tx.link_init.eq(1),
            tx.signal_rx_ready.eq(1),
            If(rx_remote_rx_ready, NextState("ENSURE_SIGNAL_RX_READY"))
        )
        # If the transceiver transmits one character per RTIO cycle,
        # we may be unlucky and signal_rx_ready will transmit a comma
        # on the first cycle instead of a "RX ready" character.
        # Further, we need to ensure the rx.remote_rx_ready
        # gets through MultiReg to rx_remote_rx_ready at the receiver.
        # So transmit the "RX ready" pattern for several cycles.
        fsm.act("ENSURE_SIGNAL_RX_READY",
            link_status.i.eq(3),
            tx.link_init.eq(1),
            tx.signal_rx_ready.eq(1),
            signal_rx_ready_margin.wait.eq(1),
            If(signal_rx_ready_margin.done, NextState("WAIT_REMOTE_LINK_UP"))
        )
        fsm.act("WAIT_REMOTE_LINK_UP",
            link_status.i.eq(4),
            If(~rx_link_init, NextState("READY"))
        )
        fsm.act("READY",
            link_status.i.eq(5),
            If(rx_link_init, NextState("RESET_RX")),  # TODO: remove this, link deinit should be detected at upper layer
            self.ready.eq(1)
        )
