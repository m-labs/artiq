from artiq import *


class DDSTest(AutoDB):
    __artiq_unit__ = "DDS test"

    class DBKeys:
        core = Device()
        dds0 = Device()
        dds1 = Device()
        dds2 = Device()
        led = Device()

    @kernel
    def run(self):
        for i in range(10000):
            if i & 0x200:
                self.led.on()
            else:
                self.led.off()
            with parallel:
                with sequential:
                    self.dds0.pulse(100*MHz + 4*i*kHz, 500*us)
                    self.dds1.pulse(120*MHz, 500*us)
                self.dds2.pulse(200*MHz, 100*us)
        self.led.off()
