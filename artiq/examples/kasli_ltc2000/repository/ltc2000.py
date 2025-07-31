from artiq.experiment import *
from artiq.language.units import us, ms

class DAC_Init(EnvExperiment):
    MHz = 1e6

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ltc_trigger")
        self.setattr_device("ltc_dds0")
        self.setattr_device("ltc_dds1")
        self.setattr_device("ltc_clear")

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        self.ltc_dds0.init()
        self.ltc_clear.clear(1)
        self.ltc_dds0.set_waveform(32768, 0, 0, 0, 0, 0x01000000, 0)
        self.ltc_dds1.set_waveform(0, 0, 0, 0, 0, 0x02000000, 0)
        self.ltc_trigger.trigger(0b1111)
        delay(1000*us)
        self.ltc_clear.clear(0)