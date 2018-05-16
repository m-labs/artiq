import unittest
import random

from migen import *

from artiq.gateware.serwb import scrambler
from artiq.gateware.serwb import core

from misoc.interconnect import stream
from misoc.interconnect.wishbone import SRAM


class FakeInit(Module):
    def __init__(self):
        self.ready = Signal(reset=1)


class FakeSerdes(Module):
    def __init__(self):
        self.tx_ce = Signal()
        self.tx_k = Signal(4)
        self.tx_d = Signal(32)
        self.rx_ce = Signal()
        self.rx_k = Signal(4)
        self.rx_d = Signal(32)

        # # #

        data_ce = Signal(5, reset=0b00001)
        self.sync += data_ce.eq(Cat(data_ce[1:], data_ce[0]))

        self.comb += [
            self.tx_ce.eq(data_ce[0]),
            self.rx_ce.eq(data_ce[0])
        ]

class FakePHY(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint([("data", 32)])
        self.source = source = stream.Endpoint([("data", 32)])

        # # #

        self.submodules.init = FakeInit()
        self.submodules.serdes = FakeSerdes()

        # tx dataflow
        self.comb += \
            If(self.init.ready,
                sink.ack.eq(self.serdes.tx_ce),
                If(sink.stb,
                    self.serdes.tx_d.eq(sink.data)
                )
            )

        # rx dataflow
        self.comb += \
            If(self.init.ready,
                source.stb.eq(self.serdes.rx_ce),
                source.data.eq(self.serdes.rx_d)
            )


class DUTScrambler(Module):
    def __init__(self):
        self.submodules.scrambler = scrambler.Scrambler(sync_interval=16)
        self.submodules.descrambler = scrambler.Descrambler()
        self.comb += self.scrambler.source.connect(self.descrambler.sink)


class DUTCore(Module):
    def __init__(self):
        # wishbone slave
        phy_slave = FakePHY()
        serwb_slave = core.SERWBCore(phy_slave, int(1e6), "slave")
        self.submodules += phy_slave, serwb_slave

        # wishbone master
        phy_master = FakePHY()
        serwb_master = core.SERWBCore(phy_master, int(1e6), "master")
        self.submodules += phy_master, serwb_master

        # connect phy
        self.comb += [
            phy_master.serdes.rx_ce.eq(phy_slave.serdes.tx_ce),
            phy_master.serdes.rx_k.eq(phy_slave.serdes.tx_k),
            phy_master.serdes.rx_d.eq(phy_slave.serdes.tx_d),

            phy_slave.serdes.rx_ce.eq(phy_master.serdes.tx_ce),
            phy_slave.serdes.rx_k.eq(phy_master.serdes.tx_k),
            phy_slave.serdes.rx_d.eq(phy_master.serdes.tx_d)
        ]

        # add wishbone sram to wishbone master
        sram = SRAM(1024, bus=serwb_master.etherbone.wishbone.bus)
        self.submodules += sram

        # expose wishbone slave
        self.wishbone = serwb_slave.etherbone.wishbone.bus


class TestSERWBCore(unittest.TestCase):
    def test_scrambler(self):
        def generator(dut, rand_level=50):
            # prepare test
            prng = random.Random(42)
            i = 0
            last_data = -1
            # test loop
            while i != 256:
                # stim
                yield dut.scrambler.sink.stb.eq(1)
                if (yield dut.scrambler.sink.stb) & (yield dut.scrambler.sink.ack):
                    i += 1
                yield dut.scrambler.sink.data.eq(i)

                # check
                yield dut.descrambler.source.ack.eq(prng.randrange(100) > rand_level)
                if (yield dut.descrambler.source.stb) & (yield dut.descrambler.source.ack):
                    current_data = (yield dut.descrambler.source.data)
                    if (current_data != (last_data + 1)):
                        dut.errors += 1
                    last_data = current_data

                # cycle
                yield

        dut = DUTScrambler()
        dut.errors = 0
        run_simulation(dut, generator(dut))
        self.assertEqual(dut.errors, 0)

    def test_serwb(self):
        def generator(dut):
            # prepare test
            prng = random.Random(42)
            data_base = 0x100
            data_length = 4
            datas_w = [prng.randrange(2**32) for i in range(data_length)]
            datas_r = []

            # write
            for i in range(data_length):
                yield from dut.wishbone.write(data_base + i, datas_w[i])

            # read
            for i in range(data_length):
                datas_r.append((yield from dut.wishbone.read(data_base + i)))

            # check
            for i in range(data_length):
                if datas_r[i] != datas_w[i]:
                    dut.errors += 1

        dut = DUTCore()
        dut.errors = 0
        run_simulation(dut, generator(dut))
        self.assertEqual(dut.errors, 0)
