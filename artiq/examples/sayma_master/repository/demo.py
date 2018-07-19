from artiq.experiment import *
from artiq.coredevice.fmcdio_vhdci_eem import *


class Demo(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("fmcdio_dirctl")

        self.ttls = [self.get_device("ttl" + str(i)) for i in range(8)]
        self.setattr_device("urukul0_cpld")
        self.urukul_chs = [self.get_device("urukul0_ch" + str(i)) for i in range(4)]
        self.setattr_device("zotino0")

        self.dirctl_word = (
            shiftreg_bits(1, urukul_out_pins) |
            shiftreg_bits(0, urukul_aux_out_pins) |
            shiftreg_bits(2, dio_bank0_out_pins | dio_bank1_out_pins) |
            shiftreg_bits(3, zotino_out_pins))

    @kernel
    def run(self):
        self.core.reset()
        delay(10*ms)
        self.fmcdio_dirctl.set(self.dirctl_word)
        delay(10*ms)

        self.urukul0_cpld.init()
        delay(10*ms)

        self.zotino0.init()
        delay(1*ms)
        for i in range(32):
            self.zotino0.write_dac(i, i/4)
            delay(1*ms)

        while True:
            for ttl in self.ttls:
                ttl.pulse(100*ms)
            for urukul_ch in self.urukul_chs:
                urukul_ch.sw.pulse(100*ms)
