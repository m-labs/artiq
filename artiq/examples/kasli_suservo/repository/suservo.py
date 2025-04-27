from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut
from artiq.coredevice.suservo import SUServo, Channel as SUServoChannel

@compile
class SUServoDemo(EnvExperiment):
    core: KernelInvariant[Core]
    led0: KernelInvariant[TTLOut]
    suservo0: KernelInvariant[SUServo]
    suservo0_ch0: KernelInvariant[SUServoChannel]
    suservo0_ch1: KernelInvariant[SUServoChannel]
    suservo0_ch2: KernelInvariant[SUServoChannel]
    suservo0_ch3: KernelInvariant[SUServoChannel]
    suservo0_ch4: KernelInvariant[SUServoChannel]
    suservo0_ch5: KernelInvariant[SUServoChannel]
    suservo0_ch6: KernelInvariant[SUServoChannel]
    suservo0_ch7: KernelInvariant[SUServoChannel]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("led0")
        self.setattr_device("suservo0")
        for i in range(8):
            self.setattr_device("suservo0_ch{}".format(i))

    @rpc
    def p(self, d: list[int32]):
        mask = 1 << 18 - 1
        for name, val in zip("ftw1 b1 pow cfg offset a1 ftw0 b0".split(), d):
            val = -(val & mask) + (val & ~mask)
            print("{}: {:#x} = {}".format(name, val, val))

    @rpc  # NAC3TODO (flags={"async"})
    def p1(self, adc: float, asf: float, st: int32):
        print("ADC: {:10s}, ASF: {:10s}, clipped: {}".format(
            "#"*int(adc), "#"*int(asf*10), (st >> 8) & 1), end="\r")

    @kernel
    def run(self):
        self.core.reset()
        self.led()

        self.suservo0.init()
        self.core.delay(1.*us)
        # ADC PGIA gain
        for i in range(8):
            self.suservo0.set_pgia_mu(i, 0)
            self.core.delay(10.*us)
        # DDS attenuator
        self.suservo0.cplds[0].set_att(0, 10.)
        self.core.delay(1.*us)
        # Servo is done and disabled
        assert self.suservo0.get_status() & 0xff == 2

        # set up profile 0 on channel 0:
        self.core.delay(120.*us)
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
            frequency=71.*MHz,
            phase=0.)
        # enable RF, IIR updates and profile 0
        self.suservo0_ch0.set(en_out=True, en_iir=True, profile=0)
        # enable global servo iterations
        self.suservo0.set_config(enable=True)

        # check servo enabled
        assert self.suservo0.get_status() & 0x01 == 1
        self.core.delay(10.*us)

        # read back profile data
        data = [0 for _ in range(8)]
        self.suservo0_ch0.get_profile_mu(0, data)
        self.p(data)
        self.core.delay(10.*ms)

        while True:
            self.suservo0.set_config(False)
            self.core.delay(10.*us)
            v = self.suservo0.get_adc(7)
            self.core.delay(30.*us)
            w = self.suservo0_ch0.get_y(0)
            self.core.delay(20.*us)
            x = self.suservo0.get_status()
            self.core.delay(10.*us)
            self.suservo0.set_config(True)
            self.p1(v, w, x)
            self.core.delay(20.*ms)

    @kernel
    def led(self):
        self.core.break_realtime()
        for i in range(3):
            self.led0.pulse(.1*s)
            self.core.delay(.1*s)
