from artiq.experiment import *


class AD5360Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("fmcdio_dirctl")
        self.dac = self.get_device("dac_zotino")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.core.reset()
        delay(5*ms)  # build slack for shift register set
        self.fmcdio_dirctl.set(self, 0x00008800)
        self.dac.setup_bus(write_div=30, read_div=40)
        self.dac.write_offsets()
        self.led.on()
        delay(400*us)
        self.led.off()
        self.dac.set([i << 10 for i in range(32)])
