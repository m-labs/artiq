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


class TestScrambler(unittest.TestCase):
    def test_roundtrip(self):
        seq = list(range(256))*3
        scrambled_seq = process(seq)
        descrambled_seq = process(scrambled_seq)
        self.assertNotEqual(seq, scrambled_seq)
        self.assertEqual(seq, descrambled_seq)


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

        def link_init():
            yield dut.tx.link_init.eq(1)
            yield
            yield
            yield dut.tx.link_init.eq(0)
            yield

        rt_packets = [
            [0x12459970, 0x9938cdef, 0x12340000],
            [0xabcdef00, 0x12345678],
            [0xeeeeeeee, 0xffffffff, 0x01020304, 0x11223344]
        ]
        def transmit_rt_packets():
            while not (yield dut.tx.link_init):
                yield
            while (yield dut.tx.link_init):
                yield

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
            while not (yield dut.tx.link_init):
                yield
            while (yield dut.tx.link_init):
                yield

            while True:
                packet = []
                rx_rt_packets.append(packet)
                while not (yield dut.rx.rt_frame):
                    yield
                while (yield dut.rx.rt_frame):
                    packet.append((yield dut.rx.rt_data))
                    yield

        run_simulation(dut, [link_init(),
                             transmit_rt_packets(), receive_rt_packets()])

        for packet in rx_rt_packets:
            print(" ".join("{:08x}".format(x) for x in packet))
