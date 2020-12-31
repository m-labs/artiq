from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.fsm import FSM

from artiq.gateware.rtio import rtlink
from artiq.gateware.grabber import deserializer_7series
from artiq.gateware.grabber.core import *


__all__ = ["Grabber"]


class Synchronizer(Module):
    def __init__(self, roi_engines):
        counts_in = [roi_engine.out.count for roi_engine in roi_engines]

        # This assumes all ROI engines update at the same time.
        self.update = Signal()
        # stays valid until the next frame after self.update is pulsed.
        self.counts = [Signal.like(count) for count in counts_in]

        # # #

        for count in counts_in:
            count.attr.add("no_retiming")
        self.specials += [MultiReg(i, o, "rtio") for i, o in zip(counts_in, self.counts)]

        ps = PulseSynchronizer("cl", "rtio")
        self.submodules += ps
        self.comb += ps.i.eq(roi_engines[0].out.update)
        self.sync.rtio += self.update.eq(ps.o)


class Serializer(Module):
    def __init__(self, update, counts, rtlink_i):
        self.gate = Signal(len(counts))

        # # #

        gate = Signal(len(counts))
        sentinel = 2**(len(rtlink_i.data) - 1)

        fsm = ClockDomainsRenamer("rio")(FSM())
        self.submodules += fsm

        fsm.act("INIT",
            rtlink_i.data.eq(sentinel),
            If(update & (self.gate != 0),
                NextValue(gate, self.gate),
                rtlink_i.stb.eq(1),
                NextState(0)
            )
        )
        for n, count in enumerate(counts):
            last = n == len(counts)-1
            fsm.act(n,
                rtlink_i.data.eq(count),
                rtlink_i.stb.eq(gate[n]),
                NextState("INIT" if last else n+1)
            )


class Grabber(Module):
    def __init__(self, pins, roi_engine_count=16, res_width=12, count_shift=0):
        self.config = rtlink.Interface(
            rtlink.OInterface(res_width,
                              bits_for(4*roi_engine_count-1)))
        self.gate_data = rtlink.Interface(
            rtlink.OInterface(roi_engine_count),
            rtlink.IInterface(1+ROI.count_len(res_width, count_shift),
                              timestamped=False))

        self.submodules.deserializer = deserializer_7series.Deserializer(pins)
        self.submodules.frequency_counter = FrequencyCounter()
        self.submodules.parser = Parser(res_width)
        self.comb += self.parser.cl.eq(self.deserializer.q)
        self.roi_engines = [ROI(self.parser.pix, count_shift) for _ in range(roi_engine_count)]
        self.submodules += self.roi_engines
        self.submodules.synchronizer = Synchronizer(self.roi_engines)
        self.submodules.serializer = Serializer(self.synchronizer.update, self.synchronizer.counts,
                                                self.gate_data.i)

        for n, roi_engine in enumerate(self.roi_engines):
            for offset, target in enumerate([roi_engine.cfg.x0, roi_engine.cfg.y0,
                                             roi_engine.cfg.x1, roi_engine.cfg.y1]):
                roi_boundary = Signal.like(target)
                roi_boundary.attr.add("no_retiming")
                self.sync.rtio += If(self.config.o.stb & (self.config.o.address == 4*n+offset),
                    roi_boundary.eq(self.config.o.data))
                self.specials += MultiReg(roi_boundary, target, "cl")

        self.sync.rio += If(self.gate_data.o.stb,
            self.serializer.gate.eq(self.gate_data.o.data))

    def get_csrs(self):
        return (
            self.deserializer.get_csrs() +
            self.frequency_counter.get_csrs() +
            self.parser.get_csrs())
