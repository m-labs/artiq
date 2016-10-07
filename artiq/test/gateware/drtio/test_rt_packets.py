import unittest

from migen import *

from artiq.gateware.drtio.rt_packets import *


class PacketInterface:
    def __init__(self, direction, frame, data):
        if direction == "m2s":
            self.plm = get_m2s_layouts(len(data))
        elif direction == "s2m":
            self.plm = get_s2m_layouts(len(data))
        else:
            raise ValueError
        self.frame = frame
        self.data = data

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

        ws = len(self.data)
        yield self.frame.eq(1)
        for i in range(idx//ws):
            yield self.data.eq(value)
            value >>= ws
            yield
        yield self.frame.eq(0)
        yield

    @passive
    def receive(self, callback):
        previous_frame = 0
        frame_words = []
        while True:
            frame = yield self.frame
            if frame:
                frame_words.append((yield self.data))
            if previous_frame and not frame:
                callback(frame_words)
                frame_words = []
            previous_frame = frame
            yield


class TestSatellite(unittest.TestCase):
    def test_echo(self):
        nwords = 4
        dut = RTPacketSatellite(nwords)
        pt = PacketInterface("m2s", dut.rx_rt_frame, dut.rx_rt_data)
        pr = PacketInterface("s2m", dut.tx_rt_frame, dut.tx_rt_data)
        def send():
            yield from pt.send("echo_request")
            for i in range(40):
                yield
        run_simulation(dut, [send(), pr.receive(print)])
