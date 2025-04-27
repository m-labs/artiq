from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut

@compile
class BlinkForever(EnvExperiment):
    core: KernelInvariant[Core]
    led: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.core.reset()
        while True:
            self.led.pulse(100.*ms)
            self.core.delay(100.*ms)
