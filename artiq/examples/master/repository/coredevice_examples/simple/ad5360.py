from artiq.experiment import *


class AD5360Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.dac = self.get_device("dac0")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.core.reset()
        self.dac.setup_bus(write_div=30, read_div=40)
        self.dac.write_offsets()
        self.led.on()
        delay(400*us)
        self.led.off()
        self.dac.set([i << 10 for i in range(40)])
