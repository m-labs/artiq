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

    @kernel
    def run(self):
        self.core.reset()
        self.led0.on()
        delay(5*ms)
        self.led0.off()

        self.urukul0_cpld.init()
        self.urukul0_ch0.init()
        self.urukul0_ch1.init()
        self.urukul0_ch2.init()
        self.urukul0_ch3.init()

        delay(1000*us)
        self.urukul0_ch0.set(100*MHz)
        self.urukul0_ch0.sw.on()
        self.urukul0_ch0.set_att(10.)

        delay(1000*us)
        self.urukul0_ch1.set(10*MHz, 0.5)
        self.urukul0_ch1.sw.on()
        self.urukul0_ch1.set_att(0.)

        delay(1000*us)
        self.urukul0_ch2.set(400*MHz)
        self.urukul0_ch2.sw.on()
        self.urukul0_ch2.set_att(0.)

        delay(1000*us)
        self.urukul0_ch3.set(1*MHz)
        self.urukul0_ch3.sw.on()
        self.urukul0_ch3.set_att(20.)

        while True:
            self.urukul0_ch0.sw.pulse(5*ms)
            delay(5*ms)
