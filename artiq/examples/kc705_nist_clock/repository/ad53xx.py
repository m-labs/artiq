from artiq.experiment import *


class AD53XXTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("fmcdio_dirctl")
        self.dac = self.get_device("dac_zotino")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.core.reset()
        delay(5*ms)  # build slack for shift register set
        self.fmcdio_dirctl.set(0x00008800)
        self.dac.init()
        self.led.on()
        delay(400*us)
        self.led.off()
        self.dac.set_dac_mu([i << 10 for i in range(32)])
