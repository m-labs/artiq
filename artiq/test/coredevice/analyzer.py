from artiq.language import *
from artiq.coredevice.analyzer import decode_dump, OutputMessage
from artiq.test.hardware_testbench import ExperimentCase


class CreateTTLPulse(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        self.ttl_out.pulse_mu(1000)


class AnalyzerTest(ExperimentCase):
    def test_ttl_pulse(self):
        comm = self.device_mgr.get("comm")

        # clear analyzer buffer
        comm.get_analyzer_dump()

        exp = self.create(CreateTTLPulse)
        exp.run()

        dump = decode_dump(comm.get_analyzer_dump())
        ttl_messages = [msg for msg in dump.messages
                        if isinstance(msg, OutputMessage)]
        self.assertEqual(len(ttl_messages), 2)
        self.assertEqual(
            abs(ttl_messages[0].timestamp - ttl_messages[1].timestamp),
            1000)
