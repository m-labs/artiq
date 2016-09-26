import unittest

from migen import *

from artiq.gateware.drtio.link_layer import Scrambler, Descrambler


def process(dut, seq):
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
        scrambled_seq = process(Scrambler(8), seq)
        descrambled_seq = process(Descrambler(8), scrambled_seq)
        self.assertNotEqual(seq, scrambled_seq)
        self.assertEqual(seq, descrambled_seq)

    def test_resync(self):
        seq = list(range(256))
        scrambled_seq = process(Scrambler(8), seq)
        descrambled_seq = process(Descrambler(8), scrambled_seq[20:])
        self.assertEqual(seq[100:], descrambled_seq[80:])
