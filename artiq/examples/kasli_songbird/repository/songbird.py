from artiq.experiment import *

class LtcExample(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("songbird0_trigger")
        self.setattr_device("songbird0_config")
        self.setattr_device("songbird0_dds0")
        self.setattr_device("songbird0_dds1")
        self.setattr_device("songbird0_clear")

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        self.songbird0_config.init()
        self.songbird0_clear.clear(1)
        self.songbird0_dds0.set_waveform(32768, 0, 0, 0, 0, 0x01000000, 0)
        self.songbird0_dds1.set_waveform(0, 0, 0, 0, 0, 0x02000000, 0)
        self.songbird0_trigger.trigger(0b1111)
        delay(1000*us)
        self.songbird0_clear.clear(0)