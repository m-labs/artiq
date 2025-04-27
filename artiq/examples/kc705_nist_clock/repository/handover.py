from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut


@compile
class Handover(EnvExperiment):
    core: KernelInvariant[Core]
    led: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")

    @kernel
    def blink_once(self):
        self.core.delay(250.*ms)
        self.led.pulse(250.*ms)

    def run(self):
        self.core.reset()
        while True:
            self.blink_once()
