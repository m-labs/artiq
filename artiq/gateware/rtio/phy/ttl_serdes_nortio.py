from migen import *
from migen.genlib.coding import PriorityEncoder

from artiq.gateware.rtio import rtlink


def _mk_edges(w, direction):
    l = [(1 << i) - 1 for i in range(w)]
    if direction == "rising":
        l = [((1 << w) - 1) ^ x for x in l]
    elif direction == "falling":
        pass
    else:
        raise ValueError
    return l


class _SerdesSquareWaveDriver(Module):
    def __init__(self, serdes_o, rtio_freq, wave_freq):
        assert wave_freq <= rtio_freq
        serdes_width = len(serdes_o)
        assert serdes_width & (serdes_width-1) == 0     # serdes_width must be 2**n

        edges = Array(_mk_edges(serdes_width, "rising"))
        edges_n = Array(_mk_edges(serdes_width, "falling"))

        phase_accumulator = Signal(32)
        tuning_word = int((wave_freq/rtio_freq) * 2**32)

        fine_ts = Signal()      # indicates which rtiox period within the
                                # current rtio period should the edge be changed
        logic_level = Signal(reset=1)
        logic_level_d = Signal(reset=1)
        self.comb += [
            fine_ts.eq(phase_accumulator[-log2_int(serdes_width):]),
            logic_level.eq(~phase_accumulator[-1]),
        ]
        # Using CD rio such that RtioInitRequest
        # resets the phase accumulator and logic level registers
        # (Refer to :class:`artiq.gateware.rtio.core.Core`)
        self.sync.rio += [
            logic_level_d.eq(logic_level),
            If(~logic_level_d & logic_level,
                serdes_o.eq(edges[fine_ts]),
            ).Elif(logic_level_d & ~logic_level,
                serdes_o.eq(edges_n[fine_ts]),
            ).Else(
                serdes_o.eq(Replicate(logic_level_d, serdes_width)),
            ),
            phase_accumulator.eq(phase_accumulator + tuning_word),
        ]


SEDRES_DRIVER_TYPES = {
    "square_wave": _SerdesSquareWaveDriver,
}


class Output(Module):
    def __init__(self, serdes, driver_type, **kwargs):
        assert driver_type in SEDRES_DRIVER_TYPES.keys()

        # Include an unused, dummy rtlink interface just to consume an RTIO channel
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(1, fine_ts_width=log2_int(len(serdes.o))))
        self.probes = [Signal()]
        self.overrides = [Signal(), Signal()]

        # # #

        self.submodules += SEDRES_DRIVER_TYPES[driver_type](
            serdes.o, **kwargs)


class InOut(Module):
    def __init__(self, serdes):
        raise NotImplementedError()
