from artiq.coredevice.ad9154_reg import *
from artiq.experiment import *


class Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.ad9154_spi = self.get_device("ad9154_spi0")
        self.rad9154_spi = self.get_device("rad9154_spi0")

    @kernel
    def run(self):
        self.ad9154_spi.setup_bus()
        self.rad9154_spi.setup_bus()

        for i in range(5):
            self.p("local PRODID: 0x%04x", (self.ad9154_spi.read(AD9154_PRODIDH) << 8) |
                self.ad9154_spi.read(AD9154_PRODIDL))
            self.p("remote PRODID: 0x%04x", (self.rad9154_spi.read(AD9154_PRODIDH) << 8) |
                self.rad9154_spi.read(AD9154_PRODIDL))

    def p(self, f, *a):
        print(f % a)
