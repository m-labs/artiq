from artiq.experiment import *


class SUServo(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led0")
        self.setattr_device("suservo0")
        for i in range(8):
            self.setattr_device("suservo0_ch{}".format(i))

    def run(self):
        self.init()

    def p(self, d):
        mask = 1 << 18 - 1
        for name, val in zip("ftw1 b1 pow cfg offset a1 ftw0 b0".split(), d):
            val = -(val & mask) + (val & ~mask)
            print(name, hex(val), val)

    @rpc(flags={"async"})
    def p1(self, adc, asf, st):
        print("{:10s}".format("#"*int(adc*10)))

    @kernel
    def init(self):
        self.core.break_realtime()
        self.core.reset()
        self.led()

        self.suservo0.init()
        delay(1*us)
        # ADC PGIA gain
        for i in range(8):
            self.suservo0.set_pgia_mu(i, 0)
            delay(10*us)
        # DDS attenuator
        self.suservo0.cpld0.set_att(0, 10.)
        delay(1*us)
        # Servo is done and disabled
        assert self.suservo0.get_status() & 0xff == 2

        # set up profile 0 on channel 0
        delay(100*us)
        self.suservo0_ch0.set_y(0, 0.)
        self.suservo0_ch0.set_iir(
                profile=0, adc=7, gain=-.1, corner=7000*Hz, limit=0., delay=0.)
        self.suservo0_ch0.set_dds(
                profile=0, offset=-.5, frequency=71*MHz, phase=0.)
        # enable channel
        self.suservo0_ch0.set(en_out=1, en_iir=1, profile=0)
        # enable servo iterations
        self.suservo0.set_config(enable=1)

        # read back profile data
        data = [0] * 8
        self.suservo0_ch0.get_profile_mu(0, data)
        self.p(data)
        delay(10*ms)

        # check servo enabled
        assert self.suservo0.get_status() & 0x01 == 1
        delay(10*us)

        while True:
            self.suservo0.set_config(0)
            delay(10*us)
            v = self.suservo0.get_adc(7)
            delay(30*us)
            w = self.suservo0_ch0.get_y(0)
            delay(20*us)
            x = self.suservo0.get_status()
            delay(10*us)
            self.suservo0.set_config(1)
            self.p1(v, w, x)
            delay(200*ms)

    @kernel
    def led(self):
        self.core.break_realtime()
        for i in range(3):
            self.led0.pulse(.1*s)
            delay(.1*s)
