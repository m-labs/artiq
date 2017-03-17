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
    r += encode_n(data, 4, 64)
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
        # print("{:0128x}".format(n))
        r.append(n)
    return r


test_writes = [
    (0x01, 0x23, 0x12, 0x33),
    (0x901, 0x902, 0x911, 0xeeeeeeeeeeeeeefffffffffffffffffffffffffffffff28888177772736646717738388488),
    (0x81, 0x288, 0x88, 0x8888)
]


class TB(Module):
    def __init__(self, ws):
        sequence = [b for write in test_writes for b in encode_record(*write)]
        sequence.append(0)
        # print(sequence)
        sequence = pack(sequence, ws)

        bus = wishbone.Interface(ws*8)
        self.submodules.memory = wishbone.SRAM(
            1024, init=sequence, bus=bus)
        self.submodules.dut = dma.DMA(bus)


class TestDMA(unittest.TestCase):
    def test_dma_noerror(self):
        prng = random.Random(0)
        ws = 64
        tb = TB(ws)

        def do_dma():
            for i in range(2):
                yield from tb.dut.enable.write(1)
                yield
                while ((yield from tb.dut.enable.read())):
                    yield

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

        run_simulation(tb, [do_dma(), rtio_sim()])
        self.assertEqual(received, test_writes*2)
