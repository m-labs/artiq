from artiq.language import *
from artiq.coredevice.analyzer import decode_dump, OutputMessage, InputMessage
from artiq.test.hardware_testbench import ExperimentCase


class CreateTTLPulse(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_inout")

    @kernel
    def run(self):
        self.ttl_inout.output()
        delay_mu(100)
        with parallel:
            self.ttl_inout.gate_both_mu(1200)
            with sequential:
                delay_mu(100)
                self.ttl_inout.pulse_mu(1000)
        self.ttl_inout.count()


class AnalyzerTest(ExperimentCase):
    def test_ttl_pulse(self):
        comm = self.device_mgr.get("comm")

        # clear analyzer buffer
        comm.get_analyzer_dump()

        exp = self.create(CreateTTLPulse)
        exp.run()

        dump = decode_dump(comm.get_analyzer_dump())
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
