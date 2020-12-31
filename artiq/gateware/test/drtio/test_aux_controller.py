import unittest
import random
from types import SimpleNamespace

from migen import *

from artiq.gateware.drtio.link_layer import *
from artiq.gateware.drtio.aux_controller import *


class Loopback(Module):
    def __init__(self, nwords):
        ks = [Signal() for k in range(nwords)]
        ds = [Signal(8) for d in range(nwords)]
        encoder = SimpleNamespace(k=ks, d=ds)
        decoders = [SimpleNamespace(k=k, d=d) for k, d in zip(ks, ds)]
        self.submodules.tx = LinkLayerTX(encoder)
        self.submodules.rx = LinkLayerRX(decoders)

        self.ready = Signal()

        self.tx_aux_frame = self.tx.aux_frame
        self.tx_aux_data = self.tx.aux_data
        self.tx_aux_ack = self.tx.aux_ack
        self.tx_rt_frame = self.tx.rt_frame
        self.tx_rt_data = self.tx.rt_data

        self.rx_aux_stb = self.rx.aux_stb
        self.rx_aux_frame = self.rx.aux_frame & self.ready
        self.rx_aux_data = self.rx.aux_data
        self.rx_rt_frame = self.rx.rt_frame & self.ready
        self.rx_rt_data = self.rx.rt_data


class TB(Module):
    def __init__(self, nwords):
        self.submodules.link_layer = Loopback(nwords)
        self.submodules.aux_controller = ClockDomainsRenamer(
            {"rtio": "sys", "rtio_rx": "sys"})(DRTIOAuxController(self.link_layer))


class TestAuxController(unittest.TestCase):
    def test_aux_controller(self):
        dut = TB(4)

        def link_init():
            for i in range(8):
                yield
            yield dut.link_layer.ready.eq(1)

        def send_packet(packet):
            for i, d in enumerate(packet):
                yield from dut.aux_controller.bus.write(i, d)
            yield from dut.aux_controller.transmitter.aux_tx_length.write(len(packet)*4)
            yield from dut.aux_controller.transmitter.aux_tx.write(1)
            yield
            while (yield from dut.aux_controller.transmitter.aux_tx.read()):
                yield

        def receive_packet():
            while not (yield from dut.aux_controller.receiver.aux_rx_present.read()):
                yield
            length = yield from dut.aux_controller.receiver.aux_rx_length.read()
            r = []
            for i in range(length//4):
                r.append((yield from dut.aux_controller.bus.read(256+i)))
            yield from dut.aux_controller.receiver.aux_rx_present.write(1)
            return r

        prng = random.Random(0)

        def send_and_check_packet():
            data = [prng.randrange(2**32-1) for _ in range(prng.randrange(1, 16))]
            yield from send_packet(data)
            received = yield from receive_packet()
            self.assertEqual(data, received)

        def sim():
            yield from link_init()
            for i in range(8):
                yield from send_and_check_packet()

        @passive
        def rt_traffic():
            while True:
                while prng.randrange(4):
                    yield
                yield dut.link_layer.tx_rt_frame.eq(1)
                yield
                while prng.randrange(4):
                    yield
                yield dut.link_layer.tx_rt_frame.eq(0)
                yield

        run_simulation(dut, [sim(), rt_traffic()])
