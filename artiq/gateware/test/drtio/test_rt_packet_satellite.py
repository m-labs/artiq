import unittest
from types import SimpleNamespace

from migen import *

from artiq.gateware.test.drtio.packet_interface import PacketInterface
from artiq.gateware.drtio.rt_packet_satellite import RTPacketSatellite


def create_dut(nwords):
    pt = PacketInterface("m2s", nwords*8)
    pr = PacketInterface("s2m", nwords*8)
    dut = RTPacketSatellite(SimpleNamespace(
        rx_rt_frame=pt.frame, rx_rt_data=pt.data,
        tx_rt_frame=pr.frame, tx_rt_data=pr.data))
    return pt, pr, dut


class TestSatellite(unittest.TestCase):
    def test_echo(self):
        for nwords in range(1, 8):
            pt, pr, dut = create_dut(nwords)
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
            pt, _, dut = create_dut(nwords)
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
