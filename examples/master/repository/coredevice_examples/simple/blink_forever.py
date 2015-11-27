from artiq import *


class BlinkForever(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl0")
        self.setattr_device("ttl1")

    def hello(self, i):
        print("Hello world", i)

    @kernel
    def run(self):
        for i in range(80000):
            self.ttl0.pulse(40*us)
            self.ttl1.pulse(40*us)
            delay(40*us)
        for i in range(7):
            self.hello(i)
