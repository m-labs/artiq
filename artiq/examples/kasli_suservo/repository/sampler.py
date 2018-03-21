from artiq.experiment import *


class Sampler(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("sampler0")

    def run(self):
        self.data = []
        self.sample()
        for d in self.data:
            print(d)

    @kernel
    def sample(self):
        self.core.break_realtime()
        self.sampler0.init()
        for g in range(4):
            for ch in range(8):
                self.sampler0.set_gain_mu(ch, g)
            self.ret([self.sampler0.get_gains_mu()])
            delay(10*ms)
            raw = [0] * 8
            self.sampler0.sample_mu(raw)
            self.ret(raw)
            delay(10*ms)
            data = [0.] * 8
            self.sampler0.sample(data)
            self.ret(data)
            delay(10*ms)

    @rpc(flags={"async"})
    def ret(self, data):
        self.data.append(data)
