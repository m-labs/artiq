from artiq.experiment import *


class UrukulTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("urukul0_cpld")
        self.setattr_device("urukul0_ch0")
        self.setattr_device("urukul0_ch1")
        self.setattr_device("urukul0_ch2")
        self.setattr_device("urukul0_ch3")
        self.setattr_device("led0")
        self.ttl = self.get_device("ttl16")

    @kernel
    def run(self):
        self.core.reset()
        self.ttl.output()
        delay(1*us)

        self.urukul0_cpld.init()
        self.urukul0_ch0.init()
        self.urukul0_ch1.init()
        self.urukul0_ch2.init()
        self.urukul0_ch3.init()

        delay(1000*us)
        self.urukul0_ch0.set(10*MHz)
        self.urukul0_ch0.sw.on()
        self.urukul0_ch0.set_att(10.)

        delay(1000*us)
        self.urukul0_ch1.set(20*MHz, 0.5)
        self.urukul0_ch1.sw.on()
        self.urukul0_ch1.set_att(8.)

        delay(1000*us)
        self.urukul0_ch2.set(30*MHz)
        self.urukul0_ch2.sw.on()
        self.urukul0_ch2.set_att(6.)

        delay(1000*us)
        self.urukul0_ch3.set(40*MHz)
        self.urukul0_ch3.sw.on()
        self.urukul0_ch3.set_att(4.)

        while True:
            with parallel:
                self.ttl.pulse(100*ms)
                self.urukul0_ch0.sw.pulse(100*ms)
            delay(100*ms)
            self.led0.pulse(100*ms)
