from artiq import *


class DDSTest(EnvExperiment):
    """DDS test"""

    def build(self):
        self.attr_device("core")
        self.attr_device("dds_bus")
        self.attr_device("dds0")
        self.attr_device("dds1")
        self.attr_device("dds2")
        self.attr_device("ttl0")
        self.attr_device("ttl1")
        self.attr_device("ttl2")
        self.attr_device("led")

    @kernel
    def run(self):
        with self.dds_bus.batch:
            self.dds1.set(120*MHz)
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
