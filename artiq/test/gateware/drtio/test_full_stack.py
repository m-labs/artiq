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
        self.transceivers = DummyTransceiverPair(2)
        
        self.submodules.master = DRTIOMaster(self.transceivers.alice)

        rx_synchronizer = DummyRXSynchronizer()
        self.submodules.phy = ttl_simple.Output(self.ttl)
        self.submodules.satellite = DRTIOSatellite(
            self.transceivers.bob, rx_synchronizer, [rtio.Channel.from_phy(self.phy)])
        

class TestFullStack(unittest.TestCase):
    def test_full_stack(self):
        dut = DUT(2)
        kcsrs = dut.master.rt_controller.kcsrs    

        def get_fifo_level():
            for i in range(8):
                yield from kcsrs.counter_update.write(1)
                print((yield from kcsrs.counter.read()))

        run_simulation(dut, get_fifo_level(),
            {"sys": 8, "rtio": 5, "rtio_rx": 5})
