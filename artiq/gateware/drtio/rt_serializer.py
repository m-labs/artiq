"""Serializer for real-time data, common to satellite and master"""

from types import SimpleNamespace

from migen import *

__all__ = ["ReceiveDatapath", "TransmitDatapath",
           "get_m2s_layouts", "get_s2m_layouts"]


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

    def field_length(self, type_name, field_name):
        layout = self.layouts[type_name]
        for name, length in layout:
            if name == field_name:
                return length
        raise KeyError


def get_m2s_layouts(alignment):
    if alignment > 128:
        short_data_len = alignment - 128 + 16
    else:
        short_data_len = 16

    plm = PacketLayoutManager(alignment)

    plm.add_type("echo_request")
    plm.add_type("set_time", ("timestamp", 64))

    plm.add_type("write", ("timestamp", 64),
                          ("chan_sel", 24),
                          ("address", 8),
                          ("extra_data_cnt", 8),
                          ("short_data", short_data_len))
    plm.add_type("buffer_space_request", ("destination", 8))

    plm.add_type("read_request", ("chan_sel", 24), ("timeout", 64))

    return plm


def get_s2m_layouts(alignment):
    plm = PacketLayoutManager(alignment)

    plm.add_type("echo_reply")

    plm.add_type("buffer_space_reply", ("space", 16))

    plm.add_type("read_reply", ("timestamp", 64), ("data", 32))
    plm.add_type("read_reply_noevent", ("overflow", 1))  # overflow=0→timeout

    return plm


class ReceiveDatapath(Module):
    def __init__(self, frame, data, plm):
        ws = len(data)

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
            self.frame_r.eq(frame),
            self.data_r.eq(data),
            If(frame & ~self.frame_r,
                self.packet_type.eq(data[:8]),
                packet_last_n.eq(Array(lastword_per_type)[data[:8]])
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
    def __init__(self, frame, data, plm):
        ws = len(data)
        assert ws % 8 == 0
        self.ws = ws
        self.plm = plm

        self.packet_buffer = Signal(max(layout_len(l)
                                        for l in plm.layouts.values()))
        w_in_packet = len(self.packet_buffer)//ws
        self.packet_last_n = Signal(max=max(w_in_packet, 2))
        self.packet_stb = Signal()
        self.packet_last = Signal()

        self.raw_stb = Signal()
        self.raw_data = Signal(ws)

        # # #

        self.sync += frame.eq(0)

        if w_in_packet > 1:
            packet_buffer_count = Signal(max=w_in_packet)
            self.comb += self.packet_last.eq(packet_buffer_count == self.packet_last_n)
            self.sync += [
                packet_buffer_count.eq(0),
                If(self.packet_stb,
                    frame.eq(1),
                    Case(packet_buffer_count,
                         {i: data.eq(self.packet_buffer[i*ws:(i+1)*ws])
                          for i in range(w_in_packet)}),
                    packet_buffer_count.eq(packet_buffer_count + 1)
                )
            ]
        else:
            self.comb += self.packet_last.eq(1)
            self.sync += \
                If(self.packet_stb,
                    frame.eq(1),
                    data.eq(self.packet_buffer)
                )

        self.sync += [
            If(self.raw_stb,
                frame.eq(1),
                data.eq(self.raw_data)
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
            self.packet_stb.eq(1),
            self.packet_buffer.eq(value),
            self.packet_last_n.eq(idx//self.ws-1)
        ]
