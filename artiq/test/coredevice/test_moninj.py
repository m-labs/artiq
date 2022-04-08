import unittest
import asyncio
import numpy
from collections import defaultdict
from contextlib import asynccontextmanager
from unittest import IsolatedAsyncioTestCase

from artiq.coredevice.comm_moninj import *
from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()

    return wrapper


class MonInjTest(ExperimentCase):
    def test_moninj(self):
        try:
            core = self.device_mgr.get_desc("core")
            loop_out = self.device_mgr.get_desc("loop_out")
            loop_in = self.device_mgr.get_desc("loop_in")
        except KeyError as e:
            # skip if ddb does not match requirements
            raise unittest.SkipTest(
                "test device not available: `{}`".format(*e.args))
        core_host = core["arguments"]["host"]
        loop_out_channel = loop_out["arguments"]["channel"]
        loop_in_channel = loop_in["arguments"]["channel"]

        notifications = []
        injection_statuses = []

        def monitor_cb(channel, probe, value):
            notifications.append((channel, probe, value))

        def injection_status_cb(channel, override, value):
            injection_statuses.append((channel, override, value))

        loop = asyncio.get_event_loop()
        try:
            moninj_comm = CommMonInj(monitor_cb, injection_status_cb)
            loop.run_until_complete(moninj_comm.connect(core_host))
            try:
                moninj_comm.get_injection_status(loop_out_channel, TTLOverride.en.value)
                moninj_comm.monitor_probe(True, loop_in_channel, TTLProbe.level.value)
                moninj_comm.monitor_injection(True, loop_out_channel, TTLOverride.level.en.value)
                loop.run_until_complete(asyncio.sleep(0.5))
                moninj_comm.inject(loop_out_channel, TTLOverride.level.value, 0)
                moninj_comm.inject(loop_out_channel, TTLOverride.level.oe.value, 1)
                moninj_comm.inject(loop_out_channel, TTLOverride.level.en.value, 1)
                loop.run_until_complete(asyncio.sleep(0.5))
                moninj_comm.get_injection_status(loop_out_channel, TTLOverride.en.value)
                moninj_comm.inject(loop_out_channel, TTLOverride.level.value, 1)
                loop.run_until_complete(asyncio.sleep(0.5))
                moninj_comm.inject(loop_out_channel, TTLOverride.level.value, 0)
                loop.run_until_complete(asyncio.sleep(0.5))
                moninj_comm.inject(loop_out_channel, TTLOverride.level.en.value, 0)
                loop.run_until_complete(moninj_comm._writer.drain())
            finally:
                loop.run_until_complete(moninj_comm.close())
        finally:
            loop.close()

        if notifications[0][2] == 1:
            notifications = notifications[1:]
        self.assertEqual(notifications, [
            (loop_in_channel, TTLProbe.level.value, 0),
            (loop_in_channel, TTLProbe.level.value, 1),
            (loop_in_channel, TTLProbe.level.value, 0)
        ])
        self.assertEqual(injection_statuses, [
            (loop_out_channel, TTLOverride.en.value, 0),
            (loop_out_channel, TTLOverride.en.value, 0),
            (loop_out_channel, TTLOverride.en.value, 1),
            (loop_out_channel, TTLOverride.en.value, 1)
        ])


class _UrukulExperiment(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        
    @kernel
    def init_channel(self, channel):
        self.core.reset()
        self.core.break_realtime()
        channel.cpld.init()
        channel.init()

    @kernel
    def read_raw(self, channel):
        self.init_channel(channel)
        return channel.get_mu()

    @kernel
    def write_raw(self, channel, ftw: TInt64, pow: TInt32 = 0):
        self.init_channel(channel)
        channel.set_mu(ftw, pow)

    @kernel
    def write_raw_with_asf(self, channel, ftw: TInt64, pow: TInt32 = 0, asf: TInt32 = 0):
        self.init_channel(channel)
        channel.set_mu(ftw, pow, asf)

    @kernel
    def read(self, channel):
        self.init_channel(channel)
        return channel.get()

    @kernel
    def write(self, channel, freq: TFloat, phase: TFloat = 0.0):
        self.init_channel(channel)
        channel.set(freq, phase)

    @kernel
    def write_with_amp(self, channel, freq: TFloat, phase: TFloat = 0.0, amplitude: TFloat = 0.0):
        self.init_channel(channel)
        channel.set(freq, phase, amplitude)


class AD991XMonitorTest(ExperimentCase, IsolatedAsyncioTestCase):
    def get_urukuls(self):
        urukuls = defaultdict(dict)
        ddb = self.device_db.get_device_db()
        for name, desc in ddb.items():
            if isinstance(desc, dict) and desc["type"] == "local":
                module, cls = desc["module"], desc["class"]
                if (module, cls) == ("artiq.coredevice.ad9910", "AD9910"):
                    urukuls[cls][name] = self.device_mgr.get(name)
                if (module, cls) == ("artiq.coredevice.ad9912", "AD9912"):
                    urukuls[cls][name] = self.device_mgr.get(name)
        return urukuls

    def urukuls_all(self):
        return dict(*self.urukuls.values())

    def ensure_ad9910_only(self):
        if len(self.urukuls["AD9910"]) < 1:
            raise unittest.SkipTest("test device not available: no ad9910 devices")

    def ensure_ad9912_only(self):
        if len(self.urukuls["AD9912"]) < 1:
            raise unittest.SkipTest("test device not available: no ad9912 devices")

    def setUp(self):
        super().setUp()
        self.core = self.device_mgr.get_desc("core")
        self.urukuls = self.get_urukuls()
        self.kernel = self.create(_UrukulExperiment)

    @asynccontextmanager
    async def open_comm_session(self, notifications=None, core_host=None, auto_monitor=True):
        if notifications is None:
            notifications = []
        if core_host is None:
            core_host = self.core["arguments"]["host"]

        def monitor_cb(channel, probe, value):
            notifications.append((channel, probe, value))

        moninj_comm = CommMonInj(monitor_cb, lambda x, y, z: None)
        try:
            await moninj_comm.connect(core_host)
            if auto_monitor:
                self.setup_monitor(moninj_comm)
            yield moninj_comm
            await asyncio.sleep(0.5)
        finally:
            await moninj_comm._writer.drain()
            await moninj_comm.close()

    def setup_monitor(self, moninj_comm, *, reset_zero=True):
        for name, dev in self.urukuls_all().items():
            moninj_comm.monitor_probe(True, dev.bus.channel, dev.chip_select - 4)
            if reset_zero:
                self.kernel.write_raw(dev, 0)

    @async_test
    async def test_double_read(self):
        target_ftw = 0xff00ff00
        notifications_out = []
        async with self.open_comm_session(notifications_out):
            # anyone of them is okay
            name, urukul = next(iter(self.urukuls_all().items()))
            self.kernel.write_raw(urukul, target_ftw)
            for i in range(2):
                ftw = self.kernel.read_raw(urukul)[0]
        final_values = {probe: value for _, probe, value in notifications_out}
        assert final_values[urukul.chip_select - 4] == ftw == target_ftw

    @async_test
    async def test_ftw_int32(self):
        target_ftws = {
            0: 0xaabbccdd,
            1: 0xabababab,
            2: 0xabcdabcd,
            3: 0x900f009
        }
        ftws = {}
        notifications_out = []
        async with self.open_comm_session(notifications_out):
            for name, urukul in self.urukuls_all().items():
                idx = urukul.chip_select - 4
                self.kernel.write_raw(urukul, target_ftws[idx])
                ftws[idx] = self.kernel.read_raw(urukul)[0]
        final_values = {probe: value for _, probe, value in notifications_out}
        assert final_values == ftws == target_ftws

    @async_test
    async def test_ftw_int48(self):
        self.ensure_ad9912_only()

        target_ftws = {
            0: 0xffeeffeeffee,
            1: 0xfeedfeedfeed,
            2: 0xabababababab,
            3: 0xf00ba12ba2
        }
        ftws = {}
        notifications_out = []
        async with self.open_comm_session(notifications_out):
            for name, urukul in self.urukuls["AD9912"].items():
                idx = urukul.chip_select - 4
                self.kernel.write_raw(urukul, target_ftws[idx])
                ftws[idx] = self.kernel.read_raw(urukul)[0]
        final_values = {probe: value for _, probe, value in notifications_out}
        assert final_values == ftws == target_ftws

    @async_test
    async def test_frequency(self):
        target_freqs = {
            0: 15 * MHz,
            1: 42.5 * MHz,
            2: 98.765 * MHz,
            3: 128.128 * MHz
        }
        freqs = {}
        notifications_out = []
        async with self.open_comm_session(notifications_out):
            for name, urukul in self.urukuls_all().items():
                idx = urukul.chip_select - 4
                self.kernel.write(urukul, target_freqs[idx])
                freqs[idx] = self.kernel.read(urukul)[0]
        for key, value in freqs.items():
            assert numpy.isclose(value, target_freqs[key], rtol=1e-06)

    @async_test
    async def test_frequency_with_turns(self):
        target_freqs = {
            0: 15 * MHz,
            1: 42.5 * MHz,
            2: 98.765 * MHz,
            3: 128.128 * MHz
        }
        freqs = {}
        notifications_out = []
        async with self.open_comm_session(notifications_out):
            for name, urukul in self.urukuls_all().items():
                idx = urukul.chip_select - 4
                self.kernel.write(urukul, target_freqs[idx], 123.4)
                freqs[idx] = self.kernel.read(urukul)[0]
        for key, value in freqs.items():
            assert numpy.isclose(value, target_freqs[key], rtol=1e-06)

    @async_test
    async def test_ad9910_set_all(self):
        self.ensure_ad9910_only()

        target_freqs = {
            0: 10 * MHz,
            1: 11 * MHz,
            2: 12 * MHz,
            3: 13 * MHz
        }
        freqs = {}
        notifications_out = []
        async with self.open_comm_session(notifications_out):
            for name, urukul in self.urukuls_all().items():
                idx = urukul.chip_select - 4
                self.kernel.write_with_amp(urukul, target_freqs[idx], 123.4, 0.25)
                freqs[idx] = self.kernel.read(urukul)[0]
        for key, value in freqs.items():
            assert numpy.isclose(value, target_freqs[key], rtol=1e-06)
