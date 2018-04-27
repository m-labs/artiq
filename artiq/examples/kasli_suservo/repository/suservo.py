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
        # ADC PGIA gain
        self.suservo0.set_pgia_mu(0, 0)
        # DDS attenuator
        self.suservo0.cpld0.set_att_mu(0, 64)
        delay(1*us)
        assert self.suservo0.get_status() == 2
        delay(10*us)

        # set up profile 0 on channel 0
        self.suservo0_ch0.set_y_mu(0, 0)
        self.suservo0_ch0.set_iir_mu(
                profile=0, adc=0, a1=-0x800, b0=0x1000, b1=0, delay=0)
        delay(10*us)
        self.suservo0_ch0.set_dds_mu(
                profile=0, ftw=0x12345667, offset=0x1000, pow=0xaa55)
        # enable channel
        self.suservo0_ch0.set(en_out=1, en_iir=1, profile=0)
        # enable servo iterations
        self.suservo0.set_config(1)

        # read back profile data
        data = [0] * 8
        self.suservo0_ch0.get_profile_mu(0, data)
        self.p(data)
        delay(10*ms)

        # check servo status
        assert self.suservo0.get_status() == 1
        delay(10*us)

        # reach back ADC data
        print(self.suservo0.get_adc_mu(0))
        delay(10*ms)

        # read out IIR data
        print(self.suservo0_ch0.get_y_mu(0))
        delay(10*ms)

        # repeatedly clear the IIR state/integrator
        # with the ADC yielding 0's and given the profile configuration,
        # this will lead to a slow ram up of the amplitude over about 40µs
        # followed by saturation and repetition.
        while True:
            self.suservo0_ch0.set(1, 0, 0)
            delay(1*us)
            self.suservo0_ch0.set_y_mu(0, 0)
            delay(1*us)
            self.suservo0_ch0.set(1, 1, 0)
            delay(60*us)

    @kernel
    def led(self):
        self.core.break_realtime()
        for i in range(10):
            self.led0.pulse(.1*s)
            delay(.1*s)
