from artiq import *


class DDSTest(Experiment, AutoDB):
    """DDS test"""

    class DBKeys:
        core = Device()
        dds_bus = Device()
        dds0 = Device()
        dds1 = Device()
        dds2 = Device()
        ttl0 = Device()
        ttl1 = Device()
        ttl2 = Device()
        led = Device()

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
