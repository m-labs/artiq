import logging
import string
from collections import namedtuple

from migen import *
from migen.genlib import io


logger = logging.getLogger(__name__)


# all times in cycles
ADCParams = namedtuple("ADCParams", [
    "channels", # number of channels
    "lanes",    # number of SDO? data lanes
                # lanes need to be named alphabetically and contiguous
                # (e.g. [sdoa, sdob, sdoc, sdoc] or [sdoa, sdob])
    "width",    # bits to transfer per channel
    "t_cnvh",   # CNVH duration (minimum)
    "t_conv",   # CONV duration (minimum)
    "t_rtt",    # upper estimate for clock round trip time from
                # sck at the FPGA to clkout at the FPGA (cycles)
                # this avoids having synchronizers and another counter
                # to signal end-of transfer
                # and it ensures fixed latency early in the pipeline
])


class ADC(Module):
    """Multi-lane, multi-channel, triggered, source-synchronous, serial
    ADC interface.

    * Supports ADCs like the LTC2320-16.
    * Hardcoded timings.
    """
    def __init__(self, pads, params):
        self.params = p = params # ADCParams
        self.data = [Signal((p.width, True), reset_less=True)
                for i in range(p.channels)]  # retrieved ADC data
        self.start = Signal()    # start conversion and reading
        self.reading = Signal()  # data is being read (outputs are invalid)
        self.done = Signal()     # data is valid and a new conversion can
                                 # be started

        ###

        # collect sdo lines
        sdo = []
        for i in string.ascii_lowercase[:p.lanes]:
            sdo.append(getattr(pads, "sdo" + i))
        assert p.lanes == len(sdo)

        # set up counters for the four states CNVH, CONV, READ, RTT
        t_read = p.width*p.channels//p.lanes  # SDR
        assert p.lanes*t_read == p.width*p.channels
        assert all(_ > 0 for _ in (p.t_cnvh, p.t_conv, p.t_rtt))
        assert p.t_conv > 1
        count = Signal(max=max(p.t_cnvh, p.t_conv, t_read, p.t_rtt),
                reset_less=True)
        count_load = Signal.like(count)
        count_done = Signal()
        update = Signal()

        self.comb += count_done.eq(count == 0)
        self.sync += [
                count.eq(count - 1),
                If(count_done,
                    count.eq(count_load),
                )
        ]

        self.submodules.fsm = fsm = FSM("IDLE")
        fsm.act("IDLE",
                self.done.eq(1),
                If(self.start,
                    count_load.eq(p.t_cnvh - 1),
                    NextState("CNVH")
                )
        )
        fsm.act("CNVH",
                count_load.eq(p.t_conv - 1),
                pads.cnv.eq(1),
                If(count_done,
                    NextState("CONV")
                )
        )
        fsm.act("CONV",
                count_load.eq(t_read - 1),
                If(count_done,
                    NextState("READ")
                )
        )
        fsm.act("READ",
                self.reading.eq(1),
                count_load.eq(p.t_rtt - 1),
                pads.sck_en.eq(1),
                If(count_done,
                    NextState("RTT")
                )
        )
        fsm.act("RTT",  # account for sck->clkout round trip time
                self.reading.eq(1),
                If(count_done,
                    update.eq(1),
                    NextState("IDLE")
                )
        )

        try:
            sck_en_ret = pads.sck_en_ret  # simulation
        except AttributeError:
            sck_en_ret = 1

        self.clock_domains.cd_ret = ClockDomain("ret", reset_less=True)
        self.comb += self.cd_ret.clk.eq(pads.clkout)

        k = p.channels//p.lanes
        assert t_read == k*p.width
        for i, sdo in enumerate(sdo):
            sdo_sr = Signal(2*t_read)
            self.sync.ret += [
                    If(sck_en_ret,
                        sdo_sr[1:].eq(sdo_sr),
                        sdo_sr[0].eq(sdo),
                    )
            ]
            self.sync += [
                    If(update,
                        Cat(reversed([self.data[i*k + j] for j in range(k)])
                            ).eq(sdo_sr)
                    )
            ]
