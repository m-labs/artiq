from functools import reduce
from operator import xor, or_

from migen import *
from migen.genlib.fsm import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer

from misoc.interconnect.csr import *


class Scrambler(Module):
    def __init__(self, n_io1, n_io2, n_state=23, taps=[17, 22]):
        self.i1 = Signal(n_io1)
        self.o1 = Signal(n_io1)
        self.i2 = Signal(n_io2)
        self.o2 = Signal(n_io2)
        self.sel = Signal()

        # # #

        state = Signal(n_state, reset=1)

        stmts1 = []
        stmts2 = []
        for stmts, si, so in ((stmts1, self.i1, self.o1),
                              (stmts2, self.i2, self.o2)):
            curval = [state[i] for i in range(n_state)]
            for i in reversed(range(len(si))):
                out = si[i] ^ reduce(xor, [curval[tap] for tap in taps])
                stmts += [so[i].eq(out)]
                curval.insert(0, out)
                curval.pop()

            stmts += [state.eq(Cat(*curval[:n_state]))]

        self.sync += If(self.sel, stmts2).Else(stmts1)


class Descrambler(Module):
    def __init__(self, n_io1, n_io2, n_state=23, taps=[17, 22]):
        self.i1 = Signal(n_io1)
        self.o1 = Signal(n_io1)
        self.i2 = Signal(n_io2)
        self.o2 = Signal(n_io2)
        self.sel = Signal()

        # # #

        state = Signal(n_state, reset=1)

        stmts1 = []
        stmts2 = []
        for stmts, si, so in ((stmts1, self.i1, self.o1),
                              (stmts2, self.i2, self.o2)):
            curval = [state[i] for i in range(n_state)]
            for i in reversed(range(len(si))):
                flip = reduce(xor, [curval[tap] for tap in taps])
                stmts += [so[i].eq(si[i] ^ flip)]
                curval.insert(0, si[i])
                curval.pop()

            stmts += [state.eq(Cat(*curval[:n_state]))]

        self.sync += If(self.sel, stmts2).Else(stmts1)


def K(x, y):
    return (y << 5) | x


aux_coding_comma = [
    K(28, 5),
    K(28, 0),
    K(28, 1),
    K(28, 2),
    K(23, 7),
    K(27, 7),
    K(29, 7),
    K(30, 7),
]


aux_coding_nocomma = [
    K(28, 0),
    K(28, 2),
    K(28, 3),
    K(28, 4),
    K(23, 7),
    K(27, 7),
    K(29, 7),
    K(30, 7),
]


class LinkLayerTX(Module):
    def __init__(self, encoder):
        nwords = len(encoder.k)
        # nwords must be a power of 2
        assert nwords & (nwords - 1) == 0

        self.aux_frame = Signal()
        self.aux_data = Signal(2*nwords)
        self.aux_ack = Signal()

        self.rt_frame = Signal()
        self.rt_data = Signal(8*nwords)

        # # #

        # Idle and auxiliary traffic use special characters defined in the
        # aux_coding_* tables.
        # The first (or only) character uses aux_coding_comma which guarantees
        # that commas appear regularly in the absence of traffic.
        # The subsequent characters, if any (depending on the transceiver
        # serialization ratio) use aux_coding_nocomma which does not contain
        # commas. This permits aligning the comma to the first character at
        # the receiver.
        #
        # A set of 8 special characters is chosen using a 3-bit control word.
        # This control word is scrambled to reduce EMI. The control words have
        # the following meanings:
        #   100 idle/auxiliary framing
        #   0AB 2 bits of auxiliary data
        #
        # RT traffic uses D characters and is also scrambled. The aux and RT
        # scramblers are multiplicative and share the same state so that idle
        # or aux traffic can synchronize the RT descrambler.

        scrambler = Scrambler(3*nwords, 8*nwords)
        self.submodules += scrambler

        # scrambler input
        aux_data_ctl = []
        for i in range(nwords):
            aux_data_ctl.append(self.aux_data[i*2:i*2+2])
            aux_data_ctl.append(0)
        self.comb += [
            If(self.aux_frame,
                scrambler.i1.eq(Cat(*aux_data_ctl))
            ).Else(
                scrambler.i1.eq(Replicate(0b100, nwords))
            ),
            scrambler.i2.eq(self.rt_data),
            scrambler.sel.eq(self.rt_frame),
            self.aux_ack.eq(~self.rt_frame)
        ]

        # compensate for scrambler latency
        rt_frame_r = Signal()
        self.sync += rt_frame_r.eq(self.rt_frame)

        # scrambler output
        for i in range(nwords):
            scrambled_ctl = scrambler.o1[i*3:i*3+3]
            if i:
                aux_coding = aux_coding_nocomma
            else:
                aux_coding = aux_coding_comma
            self.sync += [
                encoder.k[i].eq(1),
                encoder.d[i].eq(Array(aux_coding)[scrambled_ctl])
            ]
        self.sync += \
            If(rt_frame_r,
                [k.eq(0) for k in encoder.k],
                [d.eq(scrambler.o2[i*8:i*8+8]) for i, d in enumerate(encoder.d)]
            )


class LinkLayerRX(Module):
    def __init__(self, decoders):
        nwords = len(decoders)
        # nwords must be a power of 2
        assert nwords & (nwords - 1) == 0

        self.aux_stb = Signal()
        self.aux_frame = Signal()
        self.aux_data = Signal(2*nwords)

        self.rt_frame = Signal()
        self.rt_data = Signal(8*nwords)

        # # #

        descrambler = Descrambler(3*nwords, 8*nwords)
        self.submodules += descrambler

        # scrambler input
        all_decoded_aux = []
        for i, d in enumerate(decoders):
            decoded_aux = Signal(3)
            all_decoded_aux.append(decoded_aux)

            if i:
                aux_coding = aux_coding_nocomma
            else:
                aux_coding = aux_coding_comma

            cases = {code: decoded_aux.eq(i) for i, code in enumerate(aux_coding)}
            self.comb += Case(d.d, cases).makedefault()

        self.comb += [
            descrambler.i1.eq(Cat(*all_decoded_aux)),
            descrambler.i2.eq(Cat(*[d.d for d in decoders])),
            descrambler.sel.eq(~decoders[0].k)
        ]

        # scrambler output
        self.comb += [
            self.aux_frame.eq(~descrambler.o1[2]),
            self.aux_data.eq(
                Cat(*[descrambler.o1[3*i:3*i+2] for i in range(nwords)])),
            self.rt_data.eq(descrambler.o2)
        ]
        self.sync += [
            self.aux_stb.eq(decoders[0].k),
            self.rt_frame.eq(~decoders[0].k)
        ]



class LinkLayer(Module, AutoCSR):
    def __init__(self, encoder, decoders):
        self.link_status = CSRStatus()

        # receiver locked, comma aligned, receiving valid 8b10b symbols
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

        # # #

        ready = Signal()
        ready_r = Signal()
        self.sync.rtio += ready_r.eq(ready)
        ready_rx = Signal()
        ready_r.attr.add("no_retiming")
        self.specials += MultiReg(ready_r, ready_rx, "rtio_rx")
        self.comb += [
            self.rx_aux_frame.eq(rx.aux_frame & ready_rx),
            self.rx_rt_frame.eq(rx.rt_frame & ready_rx),
        ]
        self.specials += MultiReg(ready_r, self.link_status.status)

        wait_scrambler = ClockDomainsRenamer("rtio")(WaitTimer(15))
        self.submodules += wait_scrambler

        fsm = ClockDomainsRenamer("rtio")(FSM(reset_state="WAIT_RX_READY"))
        self.submodules += fsm

        fsm.act("WAIT_RX_READY",
            If(self.rx_ready, NextState("WAIT_SCRAMBLER_SYNC"))
        )
        fsm.act("WAIT_SCRAMBLER_SYNC",
            wait_scrambler.wait.eq(1),
            If(wait_scrambler.done, NextState("READY"))
        )
        fsm.act("READY",
            ready.eq(1),
            If(~self.rx_ready, NextState("WAIT_RX_READY"))
        )
