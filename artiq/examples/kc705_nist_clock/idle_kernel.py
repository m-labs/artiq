from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut

@nac3
class IdleKernel(EnvExperiment):
    core: KernelInvariant[Core]
    led: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")

    @kernel
    def run(self):
        start_time = now_mu() + self.core.seconds_to_mu(500.*ms)
        while self.core.get_rtio_counter_mu() < start_time:
            pass
        self.core.reset()
        while True:
            self.led.pulse(250.*ms)
            self.core.delay(125.*ms)
            self.led.pulse(125.*ms)
            self.core.delay(125.*ms)
            self.led.pulse(125.*ms)
            self.core.delay(250.*ms)
