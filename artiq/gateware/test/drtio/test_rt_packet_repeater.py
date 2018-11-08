import unittest
from types import SimpleNamespace

from migen import *

from artiq.gateware.rtio import cri
from artiq.gateware.test.drtio.packet_interface import PacketInterface
from artiq.gateware.drtio.rt_packet_repeater import RTPacketRepeater


def create_dut(nwords):
    pt = PacketInterface("s2m", nwords*8)
    pr = PacketInterface("m2s", nwords*8)
    ts = Signal(64)
    dut = ClockDomainsRenamer({"rtio": "sys", "rtio_rx": "sys"})(
        RTPacketRepeater(
            SimpleNamespace(coarse_ts=ts),
            SimpleNamespace(
                rx_rt_frame=pt.frame, rx_rt_data=pt.data,
                tx_rt_frame=pr.frame, tx_rt_data=pr.data)))
    return pt, pr, ts, dut


class TestRepeater(unittest.TestCase):
    def test_set_time(self):
        nwords = 2
        pt, pr, ts, dut = create_dut(nwords)

        def send():
            yield
            yield ts.eq(0x12345678)
            yield dut.set_time_stb.eq(1)
            while not (yield dut.set_time_ack):
                yield
            yield dut.set_time_stb.eq(0)
            yield
            for _ in range(30):
                yield

        received = False
        def receive(packet_type, field_dict, trailer):
            nonlocal received
            self.assertEqual(packet_type, "set_time")
            self.assertEqual(trailer, [])
            self.assertEqual(field_dict["timestamp"], 0x12345678)
            self.assertEqual(received, False)
            received = True

        run_simulation(dut, [send(), pr.receive(receive)])
        self.assertEqual(received, True)

    def test_output(self):
        test_writes = [
            (1, 10, 21, 0x42),
            (2, 11, 34, 0x2342),
            (3, 12, 83, 0x2345566633),
            (4, 13, 25, 0x98da14959a19498ae1),
            (5, 14, 75, 0x3998a1883ae14f828ae24958ea2479)
        ]

        for nwords in range(1, 8):
            pt, pr, ts, dut = create_dut(nwords)

            def send():
                yield
                for channel, timestamp, address, data in test_writes:
                    yield dut.cri.chan_sel.eq(channel)
                    yield dut.cri.o_timestamp.eq(timestamp)
                    yield dut.cri.o_address.eq(address)
                    yield dut.cri.o_data.eq(data)
                    yield dut.cri.cmd.eq(cri.commands["write"])
                    yield
                    yield dut.cri.cmd.eq(cri.commands["nop"])
                    yield
                    for i in range(30):
                        yield
                for i in range(50):
                        yield

            short_data_len = pr.plm.field_length("write", "short_data")

            received = []
            def receive(packet_type, field_dict, trailer):
                self.assertEqual(packet_type, "write")
                self.assertEqual(len(trailer), field_dict["extra_data_cnt"]) 
                data = field_dict["short_data"]
                for n, te in enumerate(trailer):
                    data |= te << (n*nwords*8 + short_data_len)
                received.append((field_dict["chan_sel"], field_dict["timestamp"],
                                 field_dict["address"], data))

            run_simulation(dut, [send(), pr.receive(receive)])
            self.assertEqual(test_writes, received)

    def test_buffer_space(self):
        for nwords in range(1, 8):
            pt, pr, ts, dut = create_dut(nwords)

            def send_requests():
                for i in range(10):
                    yield
                    yield dut.cri.chan_sel.eq(i << 16)
                    yield dut.cri.cmd.eq(cri.commands["get_buffer_space"])
                    yield
                    yield dut.cri.cmd.eq(cri.commands["nop"])
                    yield
                    while not (yield dut.cri.o_buffer_space_valid):
                        yield
                    buffer_space = yield dut.cri.o_buffer_space
                    self.assertEqual(buffer_space, 2*i)

            current_request = None

            @passive
            def send_replies():
                nonlocal current_request
                while True:
                    while current_request is None:
                        yield
                    yield from pt.send("buffer_space_reply", space=2*current_request)
                    current_request = None

            def receive(packet_type, field_dict, trailer):
                nonlocal current_request
                self.assertEqual(packet_type, "buffer_space_request")
                self.assertEqual(trailer, [])
                self.assertEqual(current_request, None)
                current_request = field_dict["destination"]

            run_simulation(dut, [send_requests(), send_replies(), pr.receive(receive)])

    def test_input(self):
        for nwords in range(1, 8):
            pt, pr, ts, dut = create_dut(nwords)

            def read(chan_sel, timeout):
                yield dut.cri.chan_sel.eq(chan_sel)
                yield dut.cri.i_timeout.eq(timeout)
                yield dut.cri.cmd.eq(cri.commands["read"])
                yield
                yield dut.cri.cmd.eq(cri.commands["nop"])
                yield
                status = yield dut.cri.i_status
                while status & 4:
                    yield
                    status = yield dut.cri.i_status
                if status & 0x1:
                    return "timeout"
                if status & 0x2:
                    return "overflow"
                if status & 0x8:
                    return "destination unreachable"
                return ((yield dut.cri.i_data),
                        (yield dut.cri.i_timestamp))

            def send_requests():
                for timeout in range(20, 200000, 100000):
                    for chan_sel in range(3):
                        data, timestamp = yield from read(chan_sel, timeout)
                        self.assertEqual(data, chan_sel*2)
                        self.assertEqual(timestamp, timeout//2)

                i2 = yield from read(10, 400000)
                self.assertEqual(i2, "timeout")
                i3 = yield from read(11, 400000)
                self.assertEqual(i3, "overflow")

            current_request = None

            @passive
            def send_replies():
                nonlocal current_request
                while True:
                    while current_request is None:
                        yield
                    chan_sel, timeout = current_request
                    if chan_sel == 10:
                        yield from pt.send("read_reply_noevent", overflow=0)
                    elif chan_sel == 11:
                        yield from pt.send("read_reply_noevent", overflow=1)
                    else:
                        yield from pt.send("read_reply", data=chan_sel*2, timestamp=timeout//2)
                    current_request = None

            def receive(packet_type, field_dict, trailer):
                nonlocal current_request
                self.assertEqual(packet_type, "read_request")
                self.assertEqual(trailer, [])
                self.assertEqual(current_request, None)
                current_request = (field_dict["chan_sel"], field_dict["timeout"])

            run_simulation(dut, [send_requests(), send_replies(), pr.receive(receive)])
