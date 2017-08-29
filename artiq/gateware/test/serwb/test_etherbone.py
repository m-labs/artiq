import unittest
import random

from migen import *

from misoc.interconnect.wishbone import SRAM
from misoc.interconnect.stream import Converter

from artiq.gateware.serwb import packet
from artiq.gateware.serwb import etherbone


class DUT(Module):
    def __init__(self):
        # wishbone slave
        slave_depacketizer = packet.Depacketizer(int(100e6))
        slave_packetizer = packet.Packetizer()
        self.submodules += slave_depacketizer, slave_packetizer
        slave_etherbone = etherbone.Etherbone(mode="slave")
        self.submodules += slave_etherbone
        self.comb += [
            slave_depacketizer.source.connect(slave_etherbone.sink),
            slave_etherbone.source.connect(slave_packetizer.sink)
        ]

        # wishbone master
        master_depacketizer = packet.Depacketizer(int(100e6))
        master_packetizer = packet.Packetizer()
        self.submodules += master_depacketizer, master_packetizer
        master_etherbone = etherbone.Etherbone(mode="master")
        master_sram = SRAM(64, bus=master_etherbone.wishbone.bus)
        self.submodules += master_etherbone, master_sram
        self.comb += [
            master_depacketizer.source.connect(master_etherbone.sink),
            master_etherbone.source.connect(master_packetizer.sink)
        ]

        # connect core directly with converters in the loop
        s2m_downconverter = Converter(32, 16)
        s2m_upconverter = Converter(16, 32)
        self.submodules += s2m_downconverter, s2m_upconverter
        m2s_downconverter = Converter(32, 16)
        m2s_upconverter = Converter(16, 32)
        self.submodules += m2s_upconverter, m2s_downconverter
        self.comb += [
        	slave_packetizer.source.connect(s2m_downconverter.sink),
        	s2m_downconverter.source.connect(s2m_upconverter.sink),
        	s2m_upconverter.source.connect(master_depacketizer.sink),

        	master_packetizer.source.connect(m2s_downconverter.sink),
        	m2s_downconverter.source.connect(m2s_upconverter.sink),
        	m2s_upconverter.source.connect(slave_depacketizer.sink)
        ]

        # expose wishbone slave
        self.wishbone = slave_etherbone.wishbone.bus


class TestEtherbone(unittest.TestCase):
    def test_write_read_sram(self):
        dut = DUT()
        prng = random.Random(1)
        def generator(dut):
            datas = [prng.randrange(0, 2**32-1) for i in range(16)]
            for i in range(16):
                yield from dut.wishbone.write(i, datas[i])
            for i in range(16):
                data = (yield from dut.wishbone.read(i))
                self.assertEqual(data, datas[i])
        run_simulation(dut, generator(dut))
