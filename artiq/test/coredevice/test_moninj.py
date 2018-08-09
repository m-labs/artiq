import unittest
import asyncio

from artiq.coredevice.comm_moninj import *
from artiq.test.hardware_testbench import ExperimentCase


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
