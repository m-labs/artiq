import unittest
from types import SimpleNamespace

from migen import *

from artiq.gateware.drtio import *
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.coredevice.exceptions import *


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
        self.ttl0 = Signal()
        self.ttl1 = Signal()
        self.transceivers = DummyTransceiverPair(nwords)
        
        self.submodules.master = DRTIOMaster(self.transceivers.alice)

        rx_synchronizer = DummyRXSynchronizer()
        self.submodules.phy0 = ttl_simple.Output(self.ttl0)
        self.submodules.phy1 = ttl_simple.Output(self.ttl1)
        rtio_channels = [
            rtio.Channel.from_phy(self.phy0),
            rtio.Channel.from_phy(self.phy1)
        ]
        self.submodules.satellite = DRTIOSatellite(
            self.transceivers.bob, rx_synchronizer, rtio_channels)
        

class TestFullStack(unittest.TestCase):
    def test_full_stack(self):
        dut = DUT(2)
        kcsrs = dut.master.rt_controller.kcsrs

        now = 0
        def delay(dt):
            nonlocal now
            now += dt

        def get_fifo_space(channel):
            yield from kcsrs.chan_sel.write(channel)
            yield from kcsrs.o_get_fifo_space.write(1)
            yield
            while (yield from kcsrs.o_status.read()) & 1:
                yield
            return (yield from kcsrs.o_dbg_fifo_space.read())

        def write(channel, data):
            yield from kcsrs.chan_sel.write(channel)
            yield from kcsrs.o_timestamp.write(now)
            yield from kcsrs.o_data.write(data)
            yield from kcsrs.o_we.write(1)
            yield
            status = 1
            while status:
                status = yield from kcsrs.o_status.read()
                if status & 2:
                    yield from kcsrs.o_underflow_reset.write(1)
                    raise RTIOUnderflow
                if status & 4:
                    yield from kcsrs.o_sequence_error_reset.write(1)
                    raise RTIOSequenceError
                yield

        def test():
            yield from get_fifo_space(0)
            yield from get_fifo_space(1)

            with self.assertRaises(RTIOUnderflow):
                yield from write(0, 0)
            
            delay(200*8)
            yield from write(0, 1)
            delay(5*8)
            yield from write(0, 0)
            yield from write(1, 1)
            delay(6*8)
            yield from write(1, 0)

            delay(-200*8)
            with self.assertRaises(RTIOSequenceError):
                yield from write(0, 1)
            delay(200*8)

            for _ in range(50):
                yield

        ttl_changes = []
        @passive
        def check_ttls():
            cycle = 0
            old_ttls = [0, 0]
            while True:
                ttls = [(yield dut.ttl0), (yield dut.ttl1)]
                for n, (old_ttl, ttl) in enumerate(zip(old_ttls, ttls)):
                    if ttl != old_ttl:
                        ttl_changes.append((cycle, n))
                old_ttls = ttls
                yield
                cycle += 1

        run_simulation(dut, 
            {"sys": test(), "rtio": check_ttls()},
            {"sys": 8, "rtio": 5, "rtio_rx": 5, "rio": 5, "rio_phy": 5}, vcd_name="foo.vcd")
        self.assertEqual(ttl_changes, [
            (203, 0),
            (208, 0),
            (208, 1),
            (214, 1)
        ])
