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
            print("{}: {:#x} = {}".format(name, val, val))

    @rpc(flags={"async"})
    def p1(self, adc, asf, st):
        print("ADC: {:10s}, ASF: {:10s}, clipped: {}".format(
            "#"*int(adc), "#"*int(asf*10), (st >> 8) & 1), end="\r")

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

        # set up profile 0 on channel 0:
        delay(120*us)
        self.suservo0_ch0.set_y(
            profile=0,
            y=0.  # clear integrator
        )
        self.suservo0_ch0.set_iir(
            profile=0,
            adc=7,  # take data from Sampler channel 7
            kp=-.1,  # -0.1 P gain
            ki=-300./s,  # low integrator gain
            g=0.,  # no integrator gain limit
            delay=0.  # no IIR update delay after enabling
        )
        # setpoint 0.5 (5 V with above PGIA gain setting)
        # 71 MHz
        # 0 phase
        self.suservo0_ch0.set_dds(
            profile=0,
            offset=-.5,  # 5 V with above PGIA settings
            frequency=71*MHz,
            phase=0.)
        # enable RF, IIR updates and profile 0
        self.suservo0_ch0.set(en_out=1, en_iir=1, profile=0)
        # enable global servo iterations
        self.suservo0.set_config(enable=1)

        # check servo enabled
        assert self.suservo0.get_status() & 0x01 == 1
        delay(10*us)

        # read back profile data
        data = [0] * 8
        self.suservo0_ch0.get_profile_mu(0, data)
        self.p(data)
        delay(10*ms)

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
            delay(20*ms)

    @kernel
    def led(self):
        self.core.break_realtime()
        for i in range(3):
            self.led0.pulse(.1*s)
            delay(.1*s)
