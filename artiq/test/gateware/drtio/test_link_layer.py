import unittest
from types import SimpleNamespace

from migen import *

from artiq.gateware.drtio.link_layer import *


def process(seq):
    dut = Scrambler(8)
    rseq = []
    def pump():
        yield dut.i.eq(seq[0])
        yield
        for w in seq[1:]:
            yield dut.i.eq(w)
            yield
            rseq.append((yield dut.o))
        yield
        rseq.append((yield dut.o))
    run_simulation(dut, pump())
    return rseq


class Loopback(Module):
    def __init__(self, nwords):
        ks = [Signal() for k in range(nwords)]
        ds = [Signal(8) for d in range(nwords)]
        encoder = SimpleNamespace(k=ks, d=ds)
        decoders = [SimpleNamespace(k=k, d=d) for k, d in zip(ks, ds)]
        self.submodules.tx = LinkLayerTX(encoder)
        self.submodules.rx = LinkLayerRX(decoders)


class TestLinkLayer(unittest.TestCase):
    def test_packets(self):
        dut = Loopback(4)

        def scrambler_sync():
            for i in range(8):
                yield

        rt_packets = [
            [0x12459970, 0x9938cdef, 0x12340000],
            [0xabcdef00, 0x12345678],
            [0xeeeeeeee, 0xffffffff, 0x01020304, 0x11223344],
            [0x88277475, 0x19883332, 0x19837662, 0x81726668, 0x81876261]
        ]
        def transmit_rt_packets():
            yield from scrambler_sync()

            for packet in rt_packets:
                yield dut.tx.rt_frame.eq(1)
                for data in packet:
                    yield dut.tx.rt_data.eq(data)
                    yield
                yield dut.tx.rt_frame.eq(0)
                yield
            # flush
            for i in range(20):
                yield

        rx_rt_packets = []
        @passive
        def receive_rt_packets():
            yield from scrambler_sync()

            previous_frame = 0
            while True:
                frame = yield dut.rx.rt_frame
                if frame and not previous_frame:
                    packet = []
                    rx_rt_packets.append(packet)
                previous_frame = frame
                if frame:
                    packet.append((yield dut.rx.rt_data))
                yield

        aux_packets = [
            [0x12, 0x34],
            [0x44, 0x11, 0x98, 0x78],
            [0xbb, 0xaa, 0xdd, 0xcc, 0x00, 0xff, 0xee]
        ]
        def transmit_aux_packets():
            yield from scrambler_sync()

            for packet in aux_packets:
                yield dut.tx.aux_frame.eq(1)
                for data in packet:
                    yield dut.tx.aux_data.eq(data)
                    yield
                    while not (yield dut.tx.aux_ack):
                        yield
                yield dut.tx.aux_frame.eq(0)
                yield
                while not (yield dut.tx.aux_ack):
                    yield
            # flush
            for i in range(20):
                yield

        rx_aux_packets = []
        @passive
        def receive_aux_packets():
            yield from scrambler_sync()

            previous_frame = 0
            while True:
                if (yield dut.rx.aux_stb):
                    frame = yield dut.rx.aux_frame
                    if frame and not previous_frame:
                        packet = []
                        rx_aux_packets.append(packet)
                    previous_frame = frame
                    if frame:
                        packet.append((yield dut.rx.aux_data))
                yield

        run_simulation(dut, [transmit_rt_packets(), receive_rt_packets(),
                             transmit_aux_packets(), receive_aux_packets()])

        # print("RT:")
        # for packet in rx_rt_packets:
        #     print(" ".join("{:08x}".format(x) for x in packet))
        # print("AUX:")
        # for packet in rx_aux_packets:
        #     print(" ".join("{:02x}".format(x) for x in packet))
        self.assertEqual(rt_packets, rx_rt_packets)
        self.assertEqual(aux_packets, rx_aux_packets)
