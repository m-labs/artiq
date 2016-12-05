import unittest

from migen import *
from misoc.interconnect import wishbone

from artiq.gateware.rtio import dma


def encode_n(n, min_length, max_length):
    r = []
    while n:
        r.append(n & 0xff)
        n >>= 8
    r += [0]*(min_length - len(r))
    if len(r) > max_length:
        raise ValueError
    return r


def encode_record(channel, timestamp, address, data):
    r = []
    r += encode_n(channel, 3, 3)
    r += encode_n(timestamp, 8, 8)
    r += encode_n(address, 2, 2)
    r += encode_n(data, 1, 64)
    return encode_n(len(r)+1, 1, 1) + r


def pack(x, size):
    r = []
    for i in range((len(x)+size-1)//size):
        n = 0
        for j, w in enumerate(x[i*size:(i+1)*size]):
            n |= w << j*8
        r.append(n)
    return r


class TB(Module):
    def __init__(self, ws):
        sequence = []
        sequence += encode_record(0x01, 0x23, 0x12, 0x33)
        sequence += encode_record(0x901, 0x902, 0x911, 0xeeeeeeeeeeeeeefffffffffffffffffffffffffffffff28888177772736646717738388488)
        sequence += encode_record(0x81, 0x288, 0x88, 0x8888)
        sequence.append(0)
        self.sequence = pack(sequence, ws)

        bus = wishbone.Interface(ws*8)
        self.submodules.memory = wishbone.SRAM(
            1024, init=self.sequence, bus=bus)
        self.submodules.dut = dma.DMA(bus)

        # TODO: remove this hack when misoc supports csr write_from_dev simulation
        self.sync += If(self.dut.enable.we, self.dut.enable.storage.eq(self.dut.enable.dat_w))


class TestDMA(unittest.TestCase):
    def test_dma(self):
        ws = 64
        tb = TB(ws)

        def gen():
            for i in range(2):
                yield from tb.dut.enable.write(1)
                for i in range(30):
                    print((yield from tb.dut.enable.read()))
                    yield

        run_simulation(tb, gen(), vcd_name="foo.vcd")
