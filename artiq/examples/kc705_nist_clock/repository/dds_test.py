from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ad9914 import AD9914
from artiq.coredevice.ttl import TTLOut


@nac3
class DDSTest(EnvExperiment):
    """DDS test"""

    core: KernelInvariant[Core]
    dds0: KernelInvariant[AD9914]
    dds1: KernelInvariant[AD9914]
    dds2: KernelInvariant[AD9914]
    ttl0: KernelInvariant[TTLOut]
    ttl1: KernelInvariant[TTLOut]
    ttl2: KernelInvariant[TTLOut]
    led: KernelInvariant[TTLOut]

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
        self.core.delay(200.*us)
        self.dds1.set(120.*MHz)
        self.core.delay(10.*us)
        self.dds2.set(200.*MHz)
        self.core.delay(1.*us)

        for i in range(10000):
            if bool(i & 0x200):
                self.led.on()
            else:
                self.led.off()
            with parallel:
                with sequential:
                    self.dds0.set(100.*MHz + 4.*float(i)*kHz)
                    self.ttl0.pulse(500.*us)
                    self.ttl1.pulse(500.*us)
                self.ttl2.pulse(100.*us)
        self.led.off()
