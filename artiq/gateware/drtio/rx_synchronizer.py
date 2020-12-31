from migen import *
from migen.genlib.cdc import ElasticBuffer


class GenericRXSynchronizer(Module):
    """Simple RX synchronizer based on the portable Migen elastic buffer.

    Introduces timing non-determinism in the satellite RX path, e.g.
    echo_request/echo_reply RTT and TSC sync, but useful for testing.
    """
    def __init__(self):
        self.signals = []

    def resync(self, signal):
        synchronized = Signal.like(signal, related=signal)
        self.signals.append((signal, synchronized))
        return synchronized

    def do_finalize(self):
        eb = ElasticBuffer(sum(len(s[0]) for s in self.signals), 4, "rtio_rx", "rtio")
        self.submodules += eb
        self.comb += [
            eb.din.eq(Cat(*[s[0] for s in self.signals])),
            Cat(*[s[1] for s in self.signals]).eq(eb.dout)
        ]


class XilinxRXSynchronizer(Module):
    """Deterministic RX synchronizer using a relatively placed macro
    to put the clock-domain-crossing FFs right next to each other.

    To meet setup/hold constraints at the receiving FFs, adjust the phase shift 
    of the jitter cleaner. 

    We assume that FPGA routing variations are small enough to be negligible.
    """
    def __init__(self):
        self.signals = []

    def resync(self, signal):
        synchronized = Signal.like(signal, related=signal)
        self.signals.append((signal, synchronized))
        return synchronized

    def do_finalize(self):
        l = sum(len(s[0]) for s in self.signals)
        din = Signal(l)
        inter = Signal(l)
        dout = Signal(l)
        self.comb += [
            din.eq(Cat(*[s[0] for s in self.signals])),
            Cat(*[s[1] for s in self.signals]).eq(dout)
        ]

        for i in range(l):
            hu_set = ("HU_SET", "drtio_rx_synchronizer")
            self.specials += [
                Instance("FD", i_C=ClockSignal("rtio_rx"), i_D=din[i], o_Q=inter[i],
                         attr={hu_set, ("RLOC", "X0Y{}".format(i))}),
                Instance("FD", i_C=ClockSignal("rtio"), i_D=inter[i], o_Q=dout[i],
                         attr={hu_set, ("RLOC", "X1Y{}".format(i))})
            ]
