from artiq.experiment import *


class BaseMod(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.basemods = [self.get_device("basemod_att0"), self.get_device("basemod_att1")]
        self.rfsws = [self.get_device("sawg_sw"+str(i)) for i in range(8)]

    @kernel
    def run(self):
        self.core.reset()
        for basemod in self.basemods:
            self.core.break_realtime()
            delay(10*ms)
            basemod.reset()
            delay(10*ms)
            basemod.set(0.0, 0.0, 0.0, 0.0)
            delay(10*ms)
            print(basemod.get_mu())

        self.core.break_realtime()
        for rfsw in self.rfsws:
            rfsw.on()
            delay(1*ms)
