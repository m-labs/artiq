from artiq.experiment import *


class SUServo(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led0")
        self.setattr_device("suservo0")
        for i in range(8):
            self.setattr_device("suservo0_ch{}".format(i))

    def run(self):
        # self.led()
        self.init()

    def p(self, d):
        for name, value in zip("ftw1 b1 pow cfg offset a1 ftw0 b0".split(), d):
            print(name, hex(value))

    @kernel
    def init(self):
        self.core.break_realtime()
        self.core.reset()

        self.suservo0.init()
        delay(1*us)
        self.suservo0.cpld0.set_att_mu(0, 255)
        delay(1*us)

        print(self.suservo0.get_status())
        delay(3*ms)

        self.suservo0_ch0.set_profile_mu(
                profile=0, ftw=0x12345667, adc=0, offset=0x10,
                a1=-0x2000, b0=0x1ffff, b1=0, delay=0, pow=0xaa55)
        self.suservo0_ch0.set(en_out=1, en_iir=1, profile=0)

        delay(10*ms)
        self.suservo0.set_config(1)
        delay(10*ms)
        data = [0] * 8
        self.suservo0_ch0.get_profile_mu(0, data)
        self.p(data)
        delay(10*ms)
        print(self.suservo0.get_adc_mu(0))
        delay(10*ms)
        print(self.suservo0.get_adc_mu(1))
        delay(10*ms)
        print(self.suservo0_ch0.get_asf_mu(0))
        delay(10*ms)
        print(self.suservo0_ch0.get_asf_mu(0))
        delay(10*ms)
        print(self.suservo0.get_status())

    @kernel
    def led(self):
        self.core.break_realtime()
        for i in range(10):
            self.led0.pulse(.1*s)
            delay(.1*s)
