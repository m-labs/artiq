from migen import *

from artiq.gateware.rtio import cri
from artiq.gateware.rtio.sed import layouts


__all__ = ["LaneDistributor"]


# CRI write happens in 3 cycles:
# 1. set timestamp and channel
# 2. set other payload elements and issue write command
# 3. check status

class LaneDistributor(Module):
    def __init__(self, lane_count, seqn_width, layout_payload, fine_ts_width,
                 enable_spread=True, quash_channels=[], interface=None):
        if lane_count & (lane_count - 1):
            raise NotImplementedError("lane count must be a power of 2")

        if interface is None:
            interface = cri.Interface()
        self.cri = interface
        self.minimum_coarse_timestamp = Signal(64-fine_ts_width)
        self.output = [Record(layouts.fifo_ingress(seqn_width, layout_payload))
                       for _ in range(lane_count)]

        # # #

        o_status_wait = Signal()
        o_status_underflow = Signal()
        o_status_sequence_error = Signal()
        self.comb += self.cri.o_status.eq(Cat(o_status_wait, o_status_underflow,
                                              o_status_sequence_error))

        # internal state
        current_lane = Signal(max=lane_count)
        last_coarse_timestamp = Signal(64-fine_ts_width)
        last_lane_coarse_timestamps = Array(Signal(64-fine_ts_width)
                                            for _ in range(lane_count))
        seqn = Signal(seqn_width)

        # distribute data to lanes
        for lio in self.output:
            self.comb += [
                lio.seqn.eq(seqn),
                lio.payload.channel.eq(self.cri.chan_sel[:16]),
                lio.payload.timestamp.eq(self.cri.timestamp),
            ]
            if hasattr(lio.payload, "address"):
                self.comb += lio.payload.address.eq(self.cri.o_address)
            if hasattr(lio.payload, "data"):
                self.comb += lio.payload.data.eq(self.cri.o_data)

        # when timestamp and channel arrive in cycle #1, prepare computations
        coarse_timestamp = Signal(64-fine_ts_width)
        self.comb += coarse_timestamp.eq(self.cri.timestamp[fine_ts_width:])
        timestamp_above_min = Signal()
        timestamp_above_laneA_min = Signal()
        timestamp_above_laneB_min = Signal()
        force_laneB = Signal()
        use_laneB = Signal()
        use_lanen = Signal(max=lane_count)
        current_lane_plus_one = Signal(max=lane_count)
        self.comb += current_lane_plus_one.eq(current_lane + 1)
        self.sync += [
            timestamp_above_min.eq(coarse_timestamp > self.minimum_coarse_timestamp),
            timestamp_above_laneA_min.eq(coarse_timestamp > last_lane_coarse_timestamps[current_lane]),
            timestamp_above_laneB_min.eq(coarse_timestamp > last_lane_coarse_timestamps[current_lane_plus_one]),
            If(force_laneB | (coarse_timestamp <= last_coarse_timestamp),
                use_lanen.eq(current_lane + 1),
                use_laneB.eq(1)
            ).Else(
                use_lanen.eq(current_lane),
                use_laneB.eq(0)
            )
        ]

        quash = Signal()
        self.sync += quash.eq(0)
        for channel in quash_channels:
            self.sync += If(self.cri.chan_sel[:16] == channel, quash.eq(1))

        # cycle #2, write
        timestamp_above_lane_min = Signal()
        do_write = Signal()
        do_underflow = Signal()
        do_sequence_error = Signal()
        self.comb += [
            timestamp_above_lane_min.eq(Mux(use_laneB, timestamp_above_laneB_min, timestamp_above_laneA_min)),
            If(~quash,
                do_write.eq((self.cri.cmd == cri.commands["write"]) & timestamp_above_min & timestamp_above_lane_min),
                do_underflow.eq((self.cri.cmd == cri.commands["write"]) & ~timestamp_above_min),
                do_sequence_error.eq((self.cri.cmd == cri.commands["write"]) & timestamp_above_min & ~timestamp_above_lane_min),
            ),
            Array(lio.we for lio in self.output)[use_lanen].eq(do_write)
        ]
        self.sync += [
            If(do_write,
                If(use_laneB, current_lane.eq(current_lane + 1)),
                last_coarse_timestamp.eq(coarse_timestamp),
                last_lane_coarse_timestamps[use_lanen].eq(coarse_timestamp),
                seqn.eq(seqn + 1),
            )
        ]

        # cycle #3, read status
        current_lane_writable = Signal()
        self.comb += [
            current_lane_writable.eq(Array(lio.writable for lio in self.output)[current_lane]),
            o_status_wait.eq(~current_lane_writable)
        ]
        self.sync += [
            If(self.cri.cmd == cri.commands["write"],
                o_status_underflow.eq(0),
                o_status_sequence_error.eq(0)
            ),
            If(do_underflow,
                o_status_underflow.eq(1)
            ),
            If(do_sequence_error,
                o_status_sequence_error.eq(1)
            )
        ]

        # current lane has been full, spread events by switching to the next.
        if enable_spread:
            current_lane_writable_r = Signal(reset=1)
            self.sync += [
                current_lane_writable_r.eq(current_lane_writable),
                If(~current_lane_writable_r & current_lane_writable,
                    force_laneB.eq(1)
                ),
                If(do_write,
                    force_laneB.eq(0)
                )
            ]
