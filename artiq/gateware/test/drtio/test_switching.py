import unittest
from types import SimpleNamespace
import random

from migen import *

from artiq.gateware.drtio import *
from artiq.gateware.drtio import rt_serializer, rt_packet_repeater
from artiq.gateware import rtio
from artiq.gateware.rtio import cri
from artiq.coredevice.exceptions import *
from artiq.gateware.test.drtio.packet_interface import PacketInterface


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


class DUT(Module):
    def __init__(self, nwords):
        self.transceivers = DummyTransceiverPair(nwords)

        self.submodules.tsc_master = rtio.TSC("async")
        self.submodules.master = DRTIOMaster(self.tsc_master,
                                             self.transceivers.alice)

        rx_synchronizer = DummyRXSynchronizer()
        self.submodules.tsc_satellite = rtio.TSC("sync")
        self.submodules.satellite = DRTIOSatellite(
            self.tsc_satellite, self.transceivers.bob, rx_synchronizer)
        self.satellite.reset.storage.reset = 0
        self.satellite.reset.storage_full.reset = 0
        self.satellite.reset_phy.storage.reset = 0
        self.satellite.reset_phy.storage_full.reset = 0

        self.pt = PacketInterface("s2m", nwords*8)
        self.pr = PacketInterface("m2s", nwords*8)
        rep_if = SimpleNamespace(
            rx_rt_frame=self.pt.frame, rx_rt_data=self.pt.data,
            tx_rt_frame=self.pr.frame, tx_rt_data=self.pr.data)
        self.submodules.repeater = rt_packet_repeater.RTPacketRepeater(
            self.tsc_satellite, rep_if)
        self.comb += self.satellite.cri.connect(self.repeater.cri)


class Testbench:
    def __init__(self):
        self.dut = DUT(2)
        self.now = 0

    def init(self, with_buffer_space=True):
        yield from self.dut.master.rt_controller.csrs.underflow_margin.write(100)
        while not (yield from self.dut.master.link_layer.rx_up.read()):
            yield
        if with_buffer_space:
            yield from self.get_buffer_space()

    def get_buffer_space(self):
        csrs = self.dut.master.rt_controller.csrs
        yield from csrs.o_get_buffer_space.write(1)
        yield
        while (yield from csrs.o_wait.read()):
            yield
        r = (yield from csrs.o_dbg_buffer_space.read())
        return r

    def delay(self, dt):
        self.now += dt

    def write(self, channel, data):
        mcri = self.dut.master.cri
        yield mcri.chan_sel.eq(channel)
        yield mcri.o_timestamp.eq(self.now)
        yield mcri.o_data.eq(data)
        yield
        yield mcri.cmd.eq(cri.commands["write"])
        yield
        yield mcri.cmd.eq(cri.commands["nop"])
        yield
        status = yield mcri.o_status
        while status & 0x1:
            yield
            status = yield mcri.o_status
        if status & 0x2:
            return "underflow"
        if status & 0x4:
            return "destination unreachable"

    def read(self, channel, timeout):
        mcri = self.dut.master.cri
        yield mcri.chan_sel.eq(channel)
        yield mcri.i_timeout.eq(timeout)
        yield
        yield mcri.cmd.eq(cri.commands["read"])
        yield
        yield mcri.cmd.eq(cri.commands["nop"])
        yield
        status = yield mcri.i_status
        while status & 0x4:
            yield
            status = yield mcri.i_status
        if status & 0x1:
            return "timeout"
        if status & 0x2:
            return "overflow"
        if status & 0x8:
            return "destination unreachable"
        return ((yield mcri.i_timestamp),
                (yield mcri.i_data))


class TestSwitching(unittest.TestCase):
    clocks = {"sys": 8, "rtio": 5, "rtio_rx": 5,
              "rio": 5, "rio_phy": 5}

    def test_outputs(self):
        tb = Testbench()

        def test():
            yield from tb.init()
            tb.delay(200)
            yield from tb.write(1, 20)
            for _ in range(40):
                yield

        current_request = None

        def get_request():
            nonlocal current_request
            while current_request is None:
                yield
            r = current_request
            current_request = None
            return r

        def expect_buffer_space_request(destination, space):
            packet_type, field_dict, trailer = yield from get_request()
            self.assertEqual(packet_type, "buffer_space_request")
            self.assertEqual(trailer, [])
            self.assertEqual(field_dict["destination"], destination)
            yield from tb.dut.pt.send("buffer_space_reply", space=space)

        def expect_write(timestamp, channel, data):
            packet_type, field_dict, trailer = yield from get_request()
            self.assertEqual(packet_type, "write")
            self.assertEqual(trailer, [])
            self.assertEqual(field_dict["timestamp"], timestamp)
            self.assertEqual(field_dict["chan_sel"], channel)
            self.assertEqual(field_dict["short_data"], data)

        @passive
        def send_replies():
            yield from expect_buffer_space_request(0, 1)
            yield from expect_write(200, 1, 20)
            yield from expect_buffer_space_request(0, 1)

            unexpected = yield from get_request()
            self.fail("unexpected packet: {}".format(unexpected))

        def receive(packet_type, field_dict, trailer):
            nonlocal current_request
            self.assertEqual(current_request, None)
            current_request = (packet_type, field_dict, trailer)

        run_simulation(tb.dut,
            {"sys": test(), "rtio": tb.dut.pr.receive(receive), "rtio_rx": send_replies()}, self.clocks)


    def test_inputs(self):
        tb = Testbench()

        def test():
            yield from tb.init(with_buffer_space=False)
            reply = yield from tb.read(19, 145)
            self.assertEqual(reply, (333, 23))
            reply = yield from tb.read(20, 146)
            self.assertEqual(reply, (334, 24))
            reply = yield from tb.read(10, 34)
            self.assertEqual(reply, "timeout")
            reply = yield from tb.read(1, 20)
            self.assertEqual(reply, "overflow")
            reply = yield from tb.read(21, 147)
            self.assertEqual(reply, (335, 25))
            for _ in range(40):
                yield

        current_request = None

        def get_request():
            nonlocal current_request
            while current_request is None:
                yield
            r = current_request
            current_request = None
            return r

        def expect_read(chan_sel, timeout, reply):
            packet_type, field_dict, trailer = yield from get_request()
            self.assertEqual(packet_type, "read_request")
            self.assertEqual(trailer, [])
            self.assertEqual(field_dict["chan_sel"], chan_sel)
            self.assertEqual(field_dict["timeout"], timeout)
            if reply == "timeout":
                yield from tb.dut.pt.send("read_reply_noevent", overflow=0)
            elif reply == "overflow":
                yield from tb.dut.pt.send("read_reply_noevent", overflow=1)
            else:
                timestamp, data = reply
                yield from tb.dut.pt.send("read_reply", timestamp=timestamp, data=data)

        @passive
        def send_replies():
            yield from expect_read(19, 145, (333, 23))
            yield from expect_read(20, 146, (334, 24))
            yield from expect_read(10, 34, "timeout")
            yield from expect_read(1, 20, "overflow")
            yield from expect_read(21, 147, (335, 25))
            unexpected = yield from get_request()
            self.fail("unexpected packet: {}".format(unexpected))

        def receive(packet_type, field_dict, trailer):
            nonlocal current_request
            self.assertEqual(current_request, None)
            current_request = (packet_type, field_dict, trailer)

        run_simulation(tb.dut,
            {"sys": test(), "rtio": tb.dut.pr.receive(receive), "rtio_rx": send_replies()}, self.clocks)
