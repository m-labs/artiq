from migen import *

from artiq.gateware.rtio import cri


def layout_lane_io(seqn_width, layout_payload):
    return [
        ("we", 1, DIR_M_TO_S),
        ("writable", 1, DIR_S_TO_M),
        ("seqn", seqn_width, DIR_M_TO_S),
        ("payload", layout_payload, DIR_M_TO_S)
    ]


# CRI write happens in 3 cycles:
# 1. set timestamp
# 2. set other payload elements and issue write command
# 3. check status

class LaneDistributor(Module):
    def __init__(self, lane_count, fifo_size, layout_payload, fine_ts_width):
        if lane_count & (lane_count - 1):
            raise NotImplementedError("lane count must be a power of 2")

        seqn_width = 4*bits_for(fifo_size-1)*lane_count

        self.cri = cri.Interface()
        self.minimum_coarse_timestamp = Signal(64-fine_ts_width)
        self.lane_io = [Record(layout_lane_io(seqn_width, layout_payload))
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
        for lio in lane_io:
            self.comb += [
                lio.seqn.eq(seqn),
                lio.payload.channel.eq(self.cri.chan_sel[:16]),
                lio.payload.timestamp.eq(self.cri.timestamp),
            ]
            if hasattr(lio.payload, "address"):
                self.comb += lio.payload.address.eq(self.cri.address)
            if hasattr(lio.payload, "data"):
                self.comb += lio.payload.data.eq(self.cri.data)

        # when timestamp arrives in cycle #1, prepare computations
        coarse_timestamp = self.cri.timestamp[fine_ts_width:]
        timestamp_above_min = Signal()
        timestamp_above_laneA_min = Signal()
        timestamp_above_laneB_min = Signal()
        use_laneB = Signal()
        use_lanen = Signal(max=lane_count)
        self.sync += [
            timestamp_above_min.eq(coarse_timestamp > self.minimum_coarse_timestamp),
            timestamp_above_laneA_min.eq(coarse_timestamp > last_lane_coarse_timestamps[current_lane]),
            timestamp_above_laneB_min.eq(coarse_timestamp > last_lane_coarse_timestamps[current_lane + 1]),
            If(coarse_timestamp <= last_coarse_timestamp,
                use_lanen.eq(current_lane + 1),
                use_laneB.eq(1)
            ).Else(
                use_lanen.eq(current_lane),
                use_laneB.eq(0)
            )
        ]

        # cycle #2, write
        timestamp_above_lane_min = Signal()
        do_write = Signal()
        do_underflow = Signal()
        do_sequence_error = Signal()
        self.comb += [
            timestamp_above_lane_min.eq(Mux(use_laneB, timestamp_above_laneB_min, timestamp_above_laneA_min)),
            do_write.eq((self.cri.cmd == cri.commands["write"]) & timestamp_above_min & timestamp_above_lane_min),
            do_underflow.eq((self.cri.cmd == cri.commands["write"]) & ~timestamp_above_min),
            do_sequence_error((self.cri.cmd == cri.commands["write"]) & timestamp_above_min & ~timestamp_above_lane_min),
            Array(lio.we for lio in lane_io)[use_lanen].eq(do_write)
        ]
        self.sync += [
            If(do_write,
                current_lane.eq(current_lane + 1),
                last_coarse_timestamp.eq(coarse_timestamp),
                last_lane_coarse_timestamps[use_lanen].eq(coarse_timestamp),
                seqn.eq(seqn + 1),
            )
        ]

        # cycle #3, read status
        current_lane_writable = Signal()
        self.comb += [
            current_lane_writable.eq((lio.writable for lio in lane_io)[current_lane]),
            o_status_wait.eq(~current_lane_writable)
        ]
        self.sync += [
            o_status_underflow.eq(do_underflow),
            o_status_sequence_error(do_sequence_error)
        ]

        # current lane has been full, spread events by switching to the next.
        current_lane_writable_r = Signal()
        self.sync += [
            current_lane_writable_r.eq(current_lane_writable),
            If(~current_lane_writable_r & current_lane_writable,
                current_lane.eq(current_lane + 1)
            )
        ]
