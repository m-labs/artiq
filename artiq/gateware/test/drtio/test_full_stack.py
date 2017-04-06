import unittest
from types import SimpleNamespace
import random

from migen import *

from artiq.gateware.drtio import *
from artiq.gateware.drtio import rt_serializer
from artiq.gateware import rtio
from artiq.gateware.rtio import rtlink
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
            rx_ready=1
        )
        self.bob = SimpleNamespace(
            encoder=SimpleNamespace(k=b2a_k, d=b2a_d),
            decoders=[SimpleNamespace(k=k, d=d) for k, d in zip(a2b_k, a2b_d)],
            rx_ready=1
        )


class DummyRXSynchronizer:
    def resync(self, signal):
        return signal


class SimpleIOPHY(Module):
    def __init__(self, o_width, i_width):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(o_width),
            rtlink.IInterface(i_width, timestamped=True))
        self.received_data = Signal(o_width)
        self.sync.rio_phy += If(self.rtlink.o.stb,
            self.received_data.eq(self.rtlink.o.data))


class DUT(Module):
    def __init__(self, nwords):
        self.ttl0 = Signal()
        self.ttl1 = Signal()
        self.transceivers = DummyTransceiverPair(nwords)

        self.submodules.master = DRTIOMaster(self.transceivers.alice)
        self.submodules.master_ki = rtio.KernelInitiator(self.master.cri)

        rx_synchronizer = DummyRXSynchronizer()
        self.submodules.phy0 = ttl_simple.Output(self.ttl0)
        self.submodules.phy1 = ttl_simple.Output(self.ttl1)
        self.submodules.phy2 = SimpleIOPHY(512, 32)  # test wide output data
        rtio_channels = [
            rtio.Channel.from_phy(self.phy0, ofifo_depth=4),
            rtio.Channel.from_phy(self.phy1, ofifo_depth=4),
            rtio.Channel.from_phy(self.phy2, ofifo_depth=4),
        ]
        self.submodules.satellite = DRTIOSatellite(
            self.transceivers.bob, rtio_channels, rx_synchronizer)
        

class TestFullStack(unittest.TestCase):
    clocks = {"sys": 8, "rtio": 5, "rtio_rx": 5,
              "rio": 5, "rio_phy": 5,
              "sys_with_rst": 8, "rtio_with_rst": 5}

    def test_outputs(self):
        dut = DUT(2)
        kcsrs = dut.master_ki
        csrs = dut.master.rt_controller.csrs
        mgr = dut.master.rt_manager
        saterr = dut.satellite.rt_errors

        ttl_changes = []
        correct_ttl_changes = [
            # from test_pulses
            (203, 0),
            (208, 0),
            (208, 1),
            (214, 1),

            # from test_fifo_space
            (414, 0),
            (454, 0),
            (494, 0),
            (534, 0),
            (574, 0),
            (614, 0)
        ]

        now = 0
        def delay(dt):
            nonlocal now
            now += dt

        def get_fifo_space(channel):
            yield from csrs.chan_sel_override_en.write(1)
            yield from csrs.chan_sel_override.write(channel)
            yield from csrs.o_get_fifo_space.write(1)
            yield
            while (yield from csrs.o_wait.read()):
                yield
            r = (yield from csrs.o_dbg_fifo_space.read())
            yield from csrs.chan_sel_override_en.write(0)
            return r

        def write(channel, data):
            yield from kcsrs.chan_sel.write(channel)
            yield from kcsrs.timestamp.write(now)
            yield from kcsrs.o_data.write(data)
            yield from kcsrs.o_we.write(1)
            yield
            status = 1
            wlen = 0
            while status:
                status = yield from kcsrs.o_status.read()
                if status & 2:
                    raise RTIOUnderflow
                if status & 4:
                    raise RTIOSequenceError
                yield
                wlen += 1
            return wlen

        def test_init():
            yield from get_fifo_space(0)
            yield from get_fifo_space(1)

        def test_underflow():
            with self.assertRaises(RTIOUnderflow):
                yield from write(0, 0)

        def test_pulses():
            delay(200*8)
            yield from write(0, 1)
            delay(5*8)
            yield from write(0, 1)
            yield from write(0, 0)  # replace
            yield from write(1, 1)
            delay(6*8)
            yield from write(1, 0)

        def test_sequence_error():
            delay(-200*8)
            with self.assertRaises(RTIOSequenceError):
                yield from write(0, 1)
            delay(200*8)

        def test_large_data():
            correct_large_data = random.Random(0).randrange(2**512-1)
            self.assertNotEqual((yield dut.phy2.received_data), correct_large_data)
            delay(10*8)
            yield from write(2, correct_large_data)
            for i in range(45):
                yield
            self.assertEqual((yield dut.phy2.received_data), correct_large_data)

        def test_fifo_space():
            delay(200*8)
            max_wlen = 0
            for _ in range(3):
                wlen = yield from write(0, 1)
                max_wlen = max(max_wlen, wlen)
                delay(40*8)
                wlen = yield from write(0, 0)
                max_wlen = max(max_wlen, wlen)
                delay(40*8)
            # check that some writes caused FIFO space requests
            self.assertGreater(max_wlen, 5)

        def test_tsc_error():
            errors = yield from saterr.protocol_error.read()
            self.assertEqual(errors, 0)
            yield from csrs.tsc_correction.write(100000000)
            yield from csrs.set_time.write(1)
            for i in range(15):
               yield
            delay(10000*8)
            yield from write(0, 1)
            for i in range(12):
               yield
            errors = yield from saterr.protocol_error.read()
            self.assertEqual(errors, 4)  # write underflow
            yield from saterr.protocol_error.write(errors)
            yield
            errors = yield from saterr.protocol_error.read()
            self.assertEqual(errors, 0)

        def wait_ttl_events():
            while len(ttl_changes) < len(correct_ttl_changes):
                yield

        def test():
            while not (yield from dut.master.link_layer.link_status.read()):
                yield

            yield from test_init()
            yield from test_underflow()
            yield from test_pulses()
            yield from test_sequence_error()
            yield from test_fifo_space()
            yield from test_large_data()
            yield from test_tsc_error()
            yield from wait_ttl_events()

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
            {"sys": test(), "rtio": check_ttls()}, self.clocks)
        self.assertEqual(ttl_changes, correct_ttl_changes)

    def test_inputs(self):
        dut = DUT(2)
        kcsrs = dut.master_ki

        def get_input(timeout):
            yield from kcsrs.chan_sel.write(2)
            yield from kcsrs.timestamp.write(10)
            yield from kcsrs.i_request.write(1)
            yield
            status = yield from kcsrs.i_status.read()
            while status & 0x4:
                yield
                status = yield from kcsrs.i_status.read()
            if status & 0x1:
                return "timeout"
            if status & 0x2:
                return "overflow"
            return ((yield from kcsrs.i_data.read()),
                    (yield from kcsrs.i_timestamp.read()))

        def test():
            # wait for link layer ready
            for i in range(5):
                yield

            i1 = yield from get_input(10)
            i2 = yield from get_input(20)
            self.assertEqual(i1, (0x600d1dea, 6))
            self.assertEqual(i2, "timeout")

        def generate_input():
            for i in range(5):
                yield
            yield dut.phy2.rtlink.i.data.eq(0x600d1dea)
            yield dut.phy2.rtlink.i.stb.eq(1)
            yield
            yield dut.phy2.rtlink.i.data.eq(0)
            yield dut.phy2.rtlink.i.stb.eq(0)

        run_simulation(dut,
            {"sys": test(), "rtio": generate_input()}, self.clocks, vcd_name="foo.vcd")

    def test_echo(self):
        dut = DUT(2)
        csrs = dut.master.rt_controller.csrs
        mgr = dut.master.rt_manager

        def test():
            while not (yield from dut.master.link_layer.link_status.read()):
                yield

            yield from mgr.update_packet_cnt.write(1)
            yield
            self.assertEqual((yield from mgr.packet_cnt_tx.read()), 0)
            self.assertEqual((yield from mgr.packet_cnt_rx.read()), 0)

            yield from mgr.request_echo.write(1)

            for i in range(15):
                yield

            yield from mgr.update_packet_cnt.write(1)
            yield
            self.assertEqual((yield from mgr.packet_cnt_tx.read()), 1)
            self.assertEqual((yield from mgr.packet_cnt_rx.read()), 1)

        run_simulation(dut, test(), self.clocks)
