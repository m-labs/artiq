import unittest
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
            {"rtio": "sys", "rtio_rx": "sys"})(AuxController(self.link_layer))


class TestAuxController(unittest.TestCase):
    def test_aux_controller(self):
        dut = TB(4)

        def gen():
            yield dut.link_layer.tx.link_init.eq(1)
            yield
            yield
            yield dut.link_layer.tx.link_init.eq(0)
            while not (yield dut.link_layer.rx.link_init):
                yield
            while (yield dut.link_layer.rx.link_init):
                yield
            yield dut.link_layer.ready.eq(1)
            yield

            yield from dut.aux_controller.bus.write(0, 0x42)
            yield from dut.aux_controller.bus.write(1, 0x23)
            yield from dut.aux_controller.transmitter.aux_tx_length.write(8)
            yield from dut.aux_controller.transmitter.aux_tx.write(1)
            for i in range(40):
                yield
            print(hex((yield from dut.aux_controller.bus.read(256))))
            print(hex((yield from dut.aux_controller.bus.read(257))))
            print((yield from dut.aux_controller.receiver.aux_rx_length.read()))

        run_simulation(dut, gen(), vcd_name="foo.vcd")
