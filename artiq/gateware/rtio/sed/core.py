from migen import *

from artiq.gateware.rtio import rtlink
from artiq.gateware.rtio.sed import layouts
from artiq.gateware.rtio.sed.lane_distributor import *
from artiq.gateware.rtio.sed.fifos import *
from artiq.gateware.rtio.sed.gates import *
from artiq.gateware.rtio.sed.output_driver import *


__all__ = ["SED"]


class SED(Module):
    def __init__(self, channels, mode, enable_spread=True, lane_count=8, fifo_depth=128, interface=None):
        if mode == "sync":
            lane_dist_cdr = lambda x: x
            fifos_cdr = lambda x: x
            gates_cdr = lambda x: x
            output_driver_cdr = lambda x: x
        elif mode == "async":
            lane_dist_cdr = ClockDomainsRenamer("rsys")
            fifos_cdr = ClockDomainsRenamer({"write": "rsys", "read": "rio"})
            gates_cdr = ClockDomainsRenamer("rio")
            output_driver_cdr = ClockDomainsRenamer("rio")
        else:
            raise ValueError

        fine_ts_width = max(rtlink.get_fine_ts_width(c.interface)
                            for c in channels)
        seqn_width = layouts.seqn_width(lane_count, fifo_depth)

        self.submodules.lane_dist = lane_dist_cdr(
            LaneDistributor(lane_count, seqn_width,
                            layouts.fifo_payload(channels), fine_ts_width,
                            enable_spread=enable_spread,
                            interface=interface))
        self.submodules.fifos = fifos_cdr(
            FIFOs(lane_count, fifo_depth,
                  layouts.fifo_payload(channels), mode))
        self.submodules.gates = gates_cdr(
            Gates(lane_count, seqn_width,
                  layouts.fifo_payload(channels),
                  layouts.output_network_payload(channels)))
        self.submodules.output_driver = output_driver_cdr(
            OutputDriver(channels, lane_count, seqn_width))

        for o, i in zip(self.lane_dist.output, self.fifos.input):
            self.comb += o.connect(i)
        for o, i in zip(self.fifos.output, self.gates.input):
            self.comb += o.connect(i)
        for o, i in zip(self.gates.output, self.output_driver.input):
            self.comb += i.eq(o)

    @property
    def cri(self):
        return self.lane_dist.cri

    @property
    def minimum_coarse_timestamp(self):
        return self.lane_dist.minimum_coarse_timestamp

    @property
    def coarse_timestamp(self):
        return self.gates.coarse_timestamp

    @property
    def collision(self):
        return self.output_driver.collision

    @property
    def collision_channel(self):
        return self.output_driver.collision_channel

    @property
    def busy(self):
        return self.output_driver.busy

    @property
    def busy_channel(self):
        return self.output_driver.busy_channel
