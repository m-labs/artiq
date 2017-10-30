from artiq.experiment import *


class DMABlink(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("led")

    @kernel
    def record(self):
        with self.core_dma.record("blink"):
            for i in range(5):
                self.led.pulse(100*ms)
                delay(100*ms)
            for i in range(5):
                self.led.pulse(50*ms)
                delay(50*ms)

    @kernel
    def run(self):
        self.core.reset()
        self.record()
        handle = self.core_dma.get_handle("blink")
        self.core.break_realtime()
        for i in range(5):
            self.core_dma.playback_handle(handle)
