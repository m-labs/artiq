import unittest
from types import SimpleNamespace

from migen import *

from artiq.gateware.drtio import *
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple


class DummyTransceiverPair:
    def __init__(self, nwords):
        a2b_k = [Signal() for _ in range(nwords)]
        a2b_d = [Signal(8) for _ in range(nwords)]
        b2a_k = [Signal() for _ in range(nwords)]
        b2a_d = [Signal(8) for _ in range(nwords)]

        self.alice = SimpleNamespace(
            encoder=SimpleNamespace(k=a2b_k, d=a2b_d),
            decoders=[SimpleNamespace(k=k, d=d) for k, d in zip(b2a_k, b2a_d)],
            rx_reset=Signal(),
            rx_ready=1
        )
        self.bob = SimpleNamespace(
            encoder=SimpleNamespace(k=b2a_k, d=b2a_d),
            decoders=[SimpleNamespace(k=k, d=d) for k, d in zip(a2b_k, a2b_d)],
            rx_reset=Signal(),
            rx_ready=1
        )


class DummyRXSynchronizer:
    def resync(self, signal):
        return signal


class DUT(Module):
    def __init__(self, nwords):
        self.ttl = Signal()
        self.transceivers = DummyTransceiverPair(nwords)
        
        self.submodules.master = DRTIOMaster(self.transceivers.alice)

        rx_synchronizer = DummyRXSynchronizer()
        self.submodules.phy = ttl_simple.Output(self.ttl)
        self.submodules.satellite = DRTIOSatellite(
            self.transceivers.bob, rx_synchronizer, [rtio.Channel.from_phy(self.phy)])
        

class TestFullStack(unittest.TestCase):
    def test_full_stack(self):
        dut = DUT(2)
        kcsrs = dut.master.rt_controller.kcsrs    

        def get_fifo_space():
            yield from kcsrs.o_get_fifo_space.write(1)
            yield
            while (yield from kcsrs.o_status.read()) & 1:
                yield
            return (yield from kcsrs.o_dbg_fifo_space.read())

        def test():
            print((yield from get_fifo_space()))
            yield from kcsrs.o_timestamp.write(550)
            yield from kcsrs.o_data.write(1)
            yield from kcsrs.o_we.write(1)
            yield
            status = 1
            while status:
                status = yield from kcsrs.o_status.read()
                print("status after write:", status)
                yield
            yield from kcsrs.o_timestamp.write(600)
            yield from kcsrs.o_data.write(0)
            yield from kcsrs.o_we.write(1)
            yield
            status = 1
            while status:
                status = yield from kcsrs.o_status.read()
                print("status after write:", status)
                yield
            for i in range(40):
                yield
            #print((yield from get_fifo_space()))

        run_simulation(dut, test(),
            {"sys": 8, "rtio": 5, "rtio_rx": 5, "rio": 5, "rio_phy": 5}, vcd_name="foo.vcd")
