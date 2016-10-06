from migen import *
from migen.genlib.fsm import *
from migen.genlib.record import *

class PacketLayoutManager:
    def __init__(self, alignment):
        self.alignment = alignment
        self.layouts = dict()
        self.types = dict()
    
    def add_type(self, name, *fields, pad=True):
        self.types[name] = len(self.types)
        layout = [("ty", 8)] + list(fields)
        misalignment = layout_len(layout) % self.alignment
        if misalignment:
            layout.append(("packet_pad", self.alignment - misalignment))
        self.layouts[name] = layout


def get_m2s_layouts(alignment):
    plm = PacketLayoutManager(alignment)
    plm.add_type("echo_request")
    plm.add_type("set_time", ("timestamp", 64))
    plm.add_type("write", ("timestamp", 64),
                          ("channel", 16),
                          ("address", 16),
                          ("data_len", 8),
                          ("short_data", 8))
    plm.add_type("fifo_level_request", ("channel", 16))
    return plm


def get_s2m_layouts(alignment):
    plm = PacketLayoutManager(alignment)
    plm.add_type("echo_reply")
    plm.add_type("fifo_level_reply", ("level", 24))
    return plm


class ReceiveDatapath(Module):
    def __init__(self, ws, plm):
        # inputs
        self.frame = Signal()
        self.data = Signal(ws)

        # control
        self.packet_buffer_load = Signal()

        # outputs
        self.frame_r = Signal()
        self.data_r = Signal()
        self.packet_type = Signal(8)
        self.packet_last = Signal()
        self.packet_as = dict()

        # # #

        # input pipeline stage - determine packet length based on type
        lastword_per_type = [layout_len(l)//ws - 1
                             for l in plm.layouts.values()]
        packet_last_n = Signal(max=max(lastword_per_type)+1)
        self.sync += [
            self.frame_r.eq(self.frame),
            self.data_r.eq(self.data),
            If(self.frame & ~self.frame_r,
                self.packet_type.eq(self.data[:8]),
                packet_last_n.eq(Array(lastword_per_type)[self.data[:8]])
            )
        ]

        # bufferize packet
        packet_buffer = Signal(max(layout_len(l)
                                   for l in plm.layouts.values()))
        w_in_packet = len(packet_buffer)//ws
        packet_buffer_count = Signal(max=w_in_packet+1)
        self.sync += \
            If(self.packet_buffer_load,
                Case(packet_buffer_count, 
                     {i: packet_buffer[i*ws:(i+1)*ws].eq(self.data_r)
                      for i in range(w_in_packet)}),
                packet_buffer_count.eq(packet_buffer_count + 1)
            ).Else(
                packet_buffer_count.eq(0)
            )
        self.comb += self.packet_last.eq(packet_buffer_count == packet_last_n)

        # cast packet
        for name, layout in plm.layouts.items():
            self.packet_as[name] = Record(layout)
            self.comb += self.packet_as[name].raw_bits().eq(packet_buffer)


class RTPacketSatellite(Module):
    def __init__(self, nwords):
        ws = 8*nwords
        self.rx_rt_frame = Signal()
        self.rx_rt_data = Signal(ws)

        self.tx_rt_frame = Signal()
        self.tx_rt_data = Signal(ws)

        # # #

        rx_plm = get_m2s_layouts(ws)
        rx_dp = ReceiveDatapath(ws, rx_plm)
        self.submodules += rx_dp
        self.comb += [
            rx_dp.frame.eq(self.rx_rt_frame),
            rx_dp.data.eq(self.rx_rt_data)
        ]

        fsm = FSM(reset_state="WAIT_FRAME")
        self.submodules += fsm

        continuation = Signal()
        continuation_r = Signal()
        frame_r_r = Signal()
        self.sync += [
            continuation_r.eq(continuation),
            frame_r_r.eq(rx_dp.frame_r)
        ]
        fsm.act("WAIT_INPUT",
            If(rx_dp.frame_r,
                If(~frame_r_r | continuation_r,
                    continuation.eq(1),
                    packet_buffer_load.eq(1),
                    If(rx_dp.packet_last,
                        Case(rx_dp.packet_type, {
                            rx_plm.types["echo_request"]: NextState("ECHO"),
                            "default": NextState("ERROR_UNKNOWN_TYPE")
                        })
                    )
                ).Else(
                    NextState("ERROR_FRAME_MISSED")
                )
            )
        )
        fsm.state("ECHO",
            NextState("WAIT_INPUT")
        )
        fsm.state("ERROR_FRAME_MISSED",
            NextState("WAIT_INPUT")
        )
        fsm.state("ERROR_UNKNOWN_TYPE",
            NextState("WAIT_INPUT")
        )
