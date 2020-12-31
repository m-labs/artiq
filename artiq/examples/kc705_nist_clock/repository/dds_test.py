from artiq.experiment import *


class DDSTest(EnvExperiment):
    """DDS test"""

    def build(self):
        self.setattr_device("core")
        self.dds0 = self.get_device("ad9914dds0")
        self.dds1 = self.get_device("ad9914dds1")
        self.dds2 = self.get_device("ad9914dds2")
        self.setattr_device("ttl0")
        self.setattr_device("ttl1")
        self.setattr_device("ttl2")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.core.reset()
        delay(200*us)
        self.dds1.set(120*MHz)
        delay(10*us)
        self.dds2.set(200*MHz)
        delay(1*us)

        for i in range(10000):
            if i & 0x200:
                self.led.on()
            else:
                self.led.off()
            with parallel:
                with sequential:
                    self.dds0.set(100*MHz + 4*i*kHz)
                    self.ttl0.pulse(500*us)
                    self.ttl1.pulse(500*us)
                self.ttl2.pulse(100*us)
        self.led.off()
