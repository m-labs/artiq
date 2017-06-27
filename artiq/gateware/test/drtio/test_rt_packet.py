import unittest
from types import SimpleNamespace
import random

from migen import *

from artiq.gateware.drtio.rt_serializer import *
from artiq.gateware.drtio.rt_packet_satellite import RTPacketSatellite
from artiq.gateware.drtio.rt_packet_master import (_CrossDomainRequest,
                                                   _CrossDomainNotification)


class PacketInterface:
    def __init__(self, direction, ws):
        if direction == "m2s":
            self.plm = get_m2s_layouts(ws)
        elif direction == "s2m":
            self.plm = get_s2m_layouts(ws)
        else:
            raise ValueError
        self.frame = Signal()
        self.data = Signal(ws)

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
                packet_type = self.plm.type_names[frame_words[0] & 0xff]
                packet_nwords = layout_len(self.plm.layouts[packet_type]) \
                                //len(self.data)
                packet, trailer = frame_words[:packet_nwords], \
                                  frame_words[packet_nwords:]

                n = 0
                packet_int = 0
                for w in packet:
                    packet_int |= (w << n)
                    n += len(self.data)

                field_dict = dict()
                idx = 0
                for field_name, field_size in self.plm.layouts[packet_type]:
                    v = (packet_int >> idx) & (2**field_size - 1)
                    field_dict[field_name] = v
                    idx += field_size

                callback(packet_type, field_dict, trailer)

                frame_words = []
            previous_frame = frame
            yield


class TestSatellite(unittest.TestCase):
    def create_dut(self, nwords):
        pt = PacketInterface("m2s", nwords*8)
        pr = PacketInterface("s2m", nwords*8)
        dut = RTPacketSatellite(SimpleNamespace(
            rx_rt_frame=pt.frame, rx_rt_data=pt.data,
            tx_rt_frame=pr.frame, tx_rt_data=pr.data))
        return pt, pr, dut

    def test_echo(self):
        for nwords in range(1, 8):
            pt, pr, dut = self.create_dut(nwords)
            completed = False
            def send():
                yield from pt.send("echo_request")
                while not completed:
                    yield
            def receive(packet_type, field_dict, trailer):
                nonlocal completed
                self.assertEqual(packet_type, "echo_reply")
                self.assertEqual(trailer, [])
                completed = True
            run_simulation(dut, [send(), pr.receive(receive)])

    def test_set_time(self):
        for nwords in range(1, 8):
            pt, _, dut = self.create_dut(nwords)
            tx_times = [0x12345678aabbccdd, 0x0102030405060708,
                        0xaabbccddeeff1122]
            def send():
                for t in tx_times:
                    yield from pt.send("set_time", timestamp=t)
                # flush
                for i in range(10):
                    yield
            rx_times = []
            @passive
            def receive():
                while True:
                    if (yield dut.tsc_load):
                        rx_times.append((yield dut.tsc_load_value))
                    yield
            run_simulation(dut, [send(), receive()])
            self.assertEqual(tx_times, rx_times)


class TestCDC(unittest.TestCase):
    def test_cross_domain_request(self):
        prng = random.Random(1)
        for sys_freq in 3, 6, 11:
            for srv_freq in 3, 6, 11:
                req_stb = Signal()
                req_ack = Signal()
                req_data = Signal(8)
                srv_stb = Signal()
                srv_ack = Signal()
                srv_data = Signal(8)
                test_seq = [93, 92, 19, 39, 91, 30, 12, 91, 38, 42]
                received_seq = []

                def requester():
                    for data in test_seq:
                        yield req_data.eq(data)
                        yield req_stb.eq(1)
                        yield
                        while not (yield req_ack):
                            yield
                        yield req_stb.eq(0)
                        for j in range(prng.randrange(0, 10)):
                            yield

                def server():
                    for i in range(len(test_seq)):
                        while not (yield srv_stb):
                            yield
                        received_seq.append((yield srv_data))
                        for j in range(prng.randrange(0, 10)):
                            yield
                        yield srv_ack.eq(1)
                        yield
                        yield srv_ack.eq(0)
                        yield

                dut = _CrossDomainRequest("srv",
                         req_stb, req_ack, req_data,
                         srv_stb, srv_ack, srv_data)
                run_simulation(dut,
                    {"sys": requester(), "srv": server()},
                    {"sys": sys_freq, "srv": srv_freq})
                self.assertEqual(test_seq, received_seq)

    def test_cross_domain_notification(self):
        prng = random.Random(1)

        emi_stb = Signal()
        emi_data = Signal(8)
        rec_stb = Signal()
        rec_ack = Signal()
        rec_data = Signal(8)

        test_seq = [23, 12, 8, 3, 28]
        received_seq = []

        def emitter():
            for data in test_seq:
                yield emi_stb.eq(1)
                yield emi_data.eq(data)
                yield
                yield emi_stb.eq(0)
                yield
                for j in range(prng.randrange(0, 3)):
                    yield

        def receiver():
            for i in range(len(test_seq)):
                while not (yield rec_stb):
                    yield
                received_seq.append((yield rec_data))
                yield rec_ack.eq(1)
                yield
                yield rec_ack.eq(0)
                yield
                for j in range(prng.randrange(0, 3)):
                    yield

        dut = _CrossDomainNotification("emi",
            emi_stb, emi_data,
            rec_stb, rec_ack, rec_data)
        run_simulation(dut,
            {"emi": emitter(), "sys": receiver()},
            {"emi": 13, "sys": 3})
        self.assertEqual(test_seq, received_seq)
