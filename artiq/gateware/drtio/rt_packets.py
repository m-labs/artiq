from types import SimpleNamespace

from migen import *
from migen.genlib.fsm import *


def layout_len(l):
    return sum(e[1] for e in l)


class PacketLayoutManager:
    def __init__(self, alignment):
        self.alignment = alignment
        self.layouts = dict()
        self.types = dict()
        self.type_names = dict()
    
    def add_type(self, name, *fields, pad=True):
        type_n = len(self.types)
        self.types[name] = type_n
        self.type_names[type_n] = name
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
    plm.add_type("error", ("code", 8))
    plm.add_type("echo_reply")
    plm.add_type("fifo_level_reply", ("level", 24))
    return plm


error_codes = {
    "frame_missed": 0,
    "unknown_type": 1
}


class ReceiveDatapath(Module):
    def __init__(self, ws, plm):
        # inputs
        self.frame = Signal()
        self.data = Signal(ws)

        # control
        self.packet_buffer_load = Signal()

        # outputs
        self.frame_r = Signal()
        self.data_r = Signal(ws)
        self.packet_type = Signal(8)
        self.packet_last = Signal()
        self.packet_as = dict()

        # # #

        # input pipeline stage - determine packet length based on type
        lastword_per_type = [layout_len(plm.layouts[plm.type_names[i]])//ws - 1
                             for i in range(len(plm.layouts))]
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

        # dissect packet
        for name, layout in plm.layouts.items():
            fields = SimpleNamespace()
            idx = 0
            for field_name, field_size in layout:
                setattr(fields, field_name, packet_buffer[idx:idx+field_size])
                idx += field_size
            self.packet_as[name] = fields


class TransmitDatapath(Module):
    def __init__(self, ws, plm):
        self.ws = ws
        self.plm = plm

        # inputs
        self.packet_buffer = Signal(max(layout_len(l)
                                        for l in plm.layouts.values()))
        w_in_packet = len(self.packet_buffer)//ws
        self.packet_len = Signal(max=w_in_packet+1)

        # control
        self.stb = Signal()
        self.done = Signal()

        # outputs
        self.frame = Signal()
        self.data = Signal(ws)

        # # #

        packet_buffer_count = Signal(max=w_in_packet+1)
        self.sync += [
            self.done.eq(0),
            self.frame.eq(0),
            packet_buffer_count.eq(0),

            If(self.stb & ~self.done,
                If(packet_buffer_count == self.packet_len,
                    self.done.eq(1)
                ).Else(
                    self.frame.eq(1),
                    Case(packet_buffer_count, 
                         {i: self.data.eq(self.packet_buffer[i*ws:(i+1)*ws])
                          for i in range(w_in_packet)}),
                    packet_buffer_count.eq(packet_buffer_count + 1)
                )
            )
        ]

    def send(self, ty, **kwargs):
        idx = 8
        value = self.plm.types[ty]
        for field_name, field_size in self.plm.layouts[ty][1:]:
            try:
                fvalue = kwargs[field_name]
                del kwargs[field_name]
            except KeyError:
                fvalue = 0
            value = value | (fvalue << idx)
            idx += field_size
        if kwargs:
            raise ValueError
        return [
            self.packet_buffer.eq(value),
            self.packet_len.eq(idx//self.ws)
        ]


class RTPacketSatellite(Module):
    def __init__(self, nwords):
        # link layer interface
        ws = 8*nwords
        self.rx_rt_frame = Signal()
        self.rx_rt_data = Signal(ws)
        self.tx_rt_frame = Signal()
        self.tx_rt_data = Signal(ws)

        # I/O Timer interface
        self.tsc_load = Signal()
        self.tsc_value = Signal(64)

        # # #

        # RX/TX datapath
        rx_plm = get_m2s_layouts(ws)
        rx_dp = ReceiveDatapath(ws, rx_plm)
        self.submodules += rx_dp
        self.comb += [
            rx_dp.frame.eq(self.rx_rt_frame),
            rx_dp.data.eq(self.rx_rt_data)
        ]
        tx_plm = get_s2m_layouts(ws)
        tx_dp = TransmitDatapath(ws, tx_plm)
        self.submodules += tx_dp
        self.comb += [
            self.tx_rt_frame.eq(tx_dp.frame),
            self.tx_rt_data.eq(tx_dp.data)
        ]

        # glue
        self.comb += [
            self.tsc_value.eq(rx_dp.packet_as["set_time"].timestamp)
        ]

        # main control FSM
        fsm = FSM(reset_state="WAIT_INPUT")
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
                    rx_dp.packet_buffer_load.eq(1),
                    If(rx_dp.packet_last,
                        Case(rx_dp.packet_type, {
                            rx_plm.types["echo_request"]: NextState("ECHO"),
                            rx_plm.types["set_time"]: NextState("SET_TIME"),
                            "default": NextState("ERROR_UNKNOWN_TYPE")
                        })
                    )
                ).Else(
                    NextState("ERROR_FRAME_MISSED")
                )
            )
        )
        fsm.act("ECHO",
            tx_dp.send("echo_reply"),
            tx_dp.stb.eq(1),
            If(tx_dp.done, NextState("WAIT_INPUT"))
        )
        fsm.act("SET_TIME",
            self.tsc_load.eq(1),
            NextState("WAIT_INPUT")
        )
        fsm.act("ERROR_FRAME_MISSED",
            tx_dp.send("error", code=error_codes["frame_missed"]),
            tx_dp.stb.eq(1),
            If(tx_dp.done, NextState("WAIT_INPUT"))
        )
        fsm.act("ERROR_UNKNOWN_TYPE",
            tx_dp.send("error", code=error_codes["unknown_type"]),
            tx_dp.stb.eq(1),
            If(tx_dp.done, NextState("WAIT_INPUT"))
        )
