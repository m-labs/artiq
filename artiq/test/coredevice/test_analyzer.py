from artiq.experiment import *
from artiq.coredevice.analyzer import (decode_dump, StoppedMessage,
                                       OutputMessage, InputMessage,
                                       _extract_log_chars)
from artiq.test.hardware_testbench import ExperimentCase


class CreateTTLPulse(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @kernel
    def initialize_io(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.off()

    @kernel
    def run(self):
        self.core.break_realtime()
        with parallel:
            self.loop_in.gate_both_mu(1200)
            with sequential:
                delay_mu(100)
                self.loop_out.pulse_mu(1000)
        self.loop_in.count()


class WriteLog(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        self.core.reset()
        rtio_log("foo", 32)


class AnalyzerTest(ExperimentCase):
    def test_ttl_pulse(self):
        comm = self.device_mgr.get("comm")

        exp = self.create(CreateTTLPulse)
        exp.initialize_io()
        comm.get_analyzer_dump()  # clear analyzer buffer
        exp.run()

        dump = decode_dump(comm.get_analyzer_dump())
        self.assertIsInstance(dump.messages[-1], StoppedMessage)
        output_messages = [msg for msg in dump.messages
                           if isinstance(msg, OutputMessage)
                              and msg.address == 0]
        self.assertEqual(len(output_messages), 2)
        self.assertEqual(
            abs(output_messages[0].timestamp - output_messages[1].timestamp),
            1000)
        input_messages = [msg for msg in dump.messages
                          if isinstance(msg, InputMessage)]
        self.assertEqual(len(input_messages), 2)
        self.assertAlmostEqual(
            abs(input_messages[0].timestamp - input_messages[1].timestamp),
            1000, delta=1)

    def test_rtio_log(self):
        comm = self.device_mgr.get("comm")

        exp = self.create(WriteLog)
        comm.get_analyzer_dump()  # clear analyzer buffer
        exp.run()

        dump = decode_dump(comm.get_analyzer_dump())
        log  = "".join([_extract_log_chars(msg.data)
                        for msg in dump.messages
                        if isinstance(msg, OutputMessage) and msg.channel == dump.log_channel])
        self.assertEqual(log, "foo\x1E32\n\x1D")
