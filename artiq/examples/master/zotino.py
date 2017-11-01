from artiq.experiment import *

class ZotinoTestDAC(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("shift_reg")
        self.setattr_device("dac_zotino")

    @kernel
    def run(self):
        self.core.reset()
        self.shift_reg.shiftreg_config(0x00008800) ## set lvds direction on fmc
        self.dac_zotino.setup_bus(write_div=30, read_div=40)
        self.dac_zotino.write_offsets()
        delay(400*us)
        self.dac_zotino.set([0x00ff for i in range(32)])
