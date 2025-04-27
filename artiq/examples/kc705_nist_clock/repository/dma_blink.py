from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.dma import CoreDMA
from artiq.coredevice.ttl import TTLOut

@compile
class DMABlink(EnvExperiment):
    core: KernelInvariant[Core]
    core_dma: KernelInvariant[CoreDMA]
    led: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("led")

    @kernel
    def record(self):
        self.core_dma.prepare_record("blink")
        with self.core_dma.recorder:
            for i in range(5):
                self.led.pulse(100.*ms)
                self.core.delay(100.*ms)
            for i in range(5):
                self.led.pulse(50.*ms)
                self.core.delay(50.*ms)

    @kernel
    def run(self):
        self.core.reset()
        self.record()
        handle = self.core_dma.get_handle("blink")
        self.core.break_realtime()
        for i in range(5):
            self.core_dma.playback_handle(handle)
