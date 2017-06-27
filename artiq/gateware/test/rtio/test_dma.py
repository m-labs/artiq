import unittest
import random

from migen import *
from misoc.interconnect import wishbone

from artiq.gateware.rtio import dma, cri


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
        for j in range(i*size, (i+1)*size):
            n <<= 8
            try:
                n |= x[j]
            except IndexError:
                pass
        r.append(n)
    return r


def encode_sequence(writes, ws):
    sequence = [b for write in writes for b in encode_record(*write)]
    sequence.append(0)
    return pack(sequence, ws)


test_writes1 = [
    (0x01, 0x23, 0x12, 0x33),
    (0x901, 0x902, 0x911, 0xeeeeeeeeeeeeeefffffffffffffffffffffffffffffff28888177772736646717738388488),
    (0x81, 0x288, 0x88, 0x8888)
]


test_writes2 = [
    (0x10, 0x10000, 0x20, 0x77),
    (0x11, 0x10001, 0x22, 0x7777),
    (0x12, 0x10002, 0x30, 0x777777),
    (0x13, 0x10003, 0x40, 0x77777788),
    (0x14, 0x10004, 0x50, 0x7777778899),
]


prng = random.Random(0)


class TB(Module):
    def __init__(self, ws):
        sequence1 = encode_sequence(test_writes1, ws)
        sequence2 = encode_sequence(test_writes2, ws)
        offset = 512//ws
        assert len(sequence1) < offset
        sequence = (
            sequence1 +
            [prng.randrange(2**(ws*8)) for _ in range(offset-len(sequence1))] +
            sequence2)

        bus = wishbone.Interface(ws*8)
        self.submodules.memory = wishbone.SRAM(
            1024, init=sequence, bus=bus)
        self.submodules.dut = dma.DMA(bus)


class TestDMA(unittest.TestCase):
    def test_dma_noerror(self):
        ws = 64
        tb = TB(ws)

        def do_dma(address):
            yield from tb.dut.dma.base_address.write(address)
            yield from tb.dut.enable.write(1)
            yield
            while ((yield from tb.dut.enable.read())):
                yield

        def do_writes():
            yield from do_dma(0)
            yield from do_dma(512)

        received = []
        @passive
        def rtio_sim():
            dut_cri = tb.dut.cri
            while True:
                cmd = yield dut_cri.cmd
                if cmd == cri.commands["nop"]:
                    pass
                elif cmd == cri.commands["write"]:
                    channel = yield dut_cri.chan_sel
                    timestamp = yield dut_cri.timestamp
                    address = yield dut_cri.o_address
                    data = yield dut_cri.o_data
                    received.append((channel, timestamp, address, data))

                    yield dut_cri.o_status.eq(1)
                    for i in range(prng.randrange(10)):
                        yield
                    yield dut_cri.o_status.eq(0)
                else:
                    self.fail("unexpected RTIO command")
                yield

        run_simulation(tb, [do_writes(), rtio_sim()])
        self.assertEqual(received, test_writes1 + test_writes2)
