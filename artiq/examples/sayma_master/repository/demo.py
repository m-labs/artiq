from artiq.experiment import *
from artiq.coredevice.fmcdio_vhdci_eem import *


class Demo(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("fmcdio_dirctl")

        self.ttls = [self.get_device("ttl" + str(i)) for i in range(8)]

        self.dirctl_word = (
            shiftreg_bits(2, dio_bank0_out_pins) |
            shiftreg_bits(2, dio_bank1_out_pins))

    @kernel
    def run(self):
        self.core.reset()
        delay(10*ms)
        self.fmcdio_dirctl.set(self.dirctl_word)
        delay(10*ms)

        while True:
            for ttl in self.ttls:
                ttl.pulse(1*ms)
