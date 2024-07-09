from migen import *

from artiq.gateware.rtio.sed import layouts
from artiq.gateware.rtio.sed.lane_distributor import *
from artiq.gateware.rtio.sed.fifos import *
from artiq.gateware.rtio.sed.gates import *
from artiq.gateware.rtio.sed.output_driver import *


__all__ = ["SED"]


class SED(Module):
    def __init__(self, channels, glbl_fine_ts_width,
                 lane_count=8, fifo_depth=128, fifo_high_watermark=1.0,
                 quash_channels=[], report_buffer_space=False, interface=None):
        seqn_width = layouts.seqn_width(lane_count, fifo_depth)

        fifo_high_watermark = int(fifo_high_watermark * fifo_depth)
        assert fifo_depth >= fifo_high_watermark

        self.submodules.lane_dist = LaneDistributor(lane_count, seqn_width,
            layouts.fifo_payload(channels),
            [channel.interface.o.delay for channel in channels],
            glbl_fine_ts_width,
            quash_channels=quash_channels,
            interface=interface)
        self.submodules.fifos = FIFOs(lane_count, fifo_depth, fifo_high_watermark,
            layouts.fifo_payload(channels), report_buffer_space)
        self.submodules.gates = Gates(lane_count, seqn_width,
            layouts.fifo_payload(channels),
            layouts.output_network_payload(channels, glbl_fine_ts_width))
        self.submodules.output_driver = OutputDriver(channels, glbl_fine_ts_width,
            lane_count, seqn_width)

        for o, i in zip(self.lane_dist.output, self.fifos.input):
            self.comb += o.connect(i)
        for o, i in zip(self.fifos.output, self.gates.input):
            self.comb += o.connect(i)
        for o, i in zip(self.gates.output, self.output_driver.input):
            self.comb += i.eq(o)

        if report_buffer_space:
            self.comb += [
                self.cri.o_buffer_space_valid.eq(1),
                self.cri.o_buffer_space.eq(self.fifos.buffer_space)
            ]

    @property
    def enable_spread(self):
        return self.lane_dist.enable_spread

    @property
    def cri(self):
        return self.lane_dist.cri

    # in CRI clock domain
    @property
    def minimum_coarse_timestamp(self):
        return self.lane_dist.minimum_coarse_timestamp

    # in I/O clock domain
    @property
    def coarse_timestamp(self):
        return self.gates.coarse_timestamp

    # in CRI clock domain
    @property
    def sequence_error(self):
        return self.lane_dist.sequence_error

    # in CRI clock domain
    @property
    def sequence_error_channel(self):
        return self.lane_dist.sequence_error_channel

    # in I/O clock domain
    @property
    def collision(self):
        return self.output_driver.collision

    # in I/O clock domain
    @property
    def collision_channel(self):
        return self.output_driver.collision_channel

    # in I/O clock domain
    @property
    def busy(self):
        return self.output_driver.busy

    # in I/O clock domain
    @property
    def busy_channel(self):
        return self.output_driver.busy_channel
