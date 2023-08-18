from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut
from artiq.coredevice.suservo import SUServo, Channel as SUServoChannel

class SUServoDemo(EnvExperiment):

    def build(self):
        self.setattr_device("core")
        self.setattr_device("led0")
        self.setattr_device("suservo0")
        self.setattr_device("suservo0_ch0")

    @kernel
    def setup_suservo(self, channel):
        self.core.break_realtime()
        channel.init()
        delay(1.*us)
        # ADC PGIA gain 0
        for i in range(8):
            channel.set_pgia_mu(i, 0)
            delay(10.*us)
        # DDS attenuator 10dB
        for i in range(4):
            for cpld in channel.cplds:
                cpld.set_att(i, 10.)
        delay(1.*us)
        # Servo is done and disabled
        # NAC3TODO assert channel.get_status() & 0xff == 2
        delay(10.*us)

    @kernel
    def setup_suservo_loop(self, channel, loop_nr):
        self.core.break_realtime()
        channel.set_y(
            profile=loop_nr,
            y=0.  # clear integrator
        )
        channel.set_iir(
            profile=loop_nr,
            adc=loop_nr,  # take data from Sampler channel
            kp=-1.,       # -1 P gain
            ki=0./s,      # no integrator gain
            g=0.,         # no integrator gain limit
            delay=0.      # no IIR update delay after enabling
        )
        # setpoint 0.5 (5 V with above PGIA gain setting)
        delay(100.*us)
        channel.set_dds(
            profile=loop_nr,
            offset=-.3,  # 3 V with above PGIA settings
            frequency=10.*MHz,
            phase=0.)
        # enable RF, IIR updates and set profile
        delay(10.*us)
        channel.set(en_out=1, en_iir=1, profile=loop_nr)

    @kernel
    def setup_start_suservo(self, channel):
        self.core.break_realtime()
        channel.set_config(enable=1)
        delay(10*us)
        # check servo enabled
        print("getting status")
        status = channel.get_status()
        if status & 0x01 == 1:
            print("status ok")
        else:
            print("status not ok")
        delay(10.*us)
        return status

    @kernel
    def run(self):
        self.core.break_realtime()
        print("hello~ just setting up the suservo for u :))")
        self.setup_suservo(self.suservo0)
        print("and now the channel!")
        self.setup_suservo_loop(self.suservo0_ch0, 0)
        print("now that it's all set up, let's start it!!!~~ :))")
        status = self.setup_start_suservo(self.suservo0)
        print("lets check the status!!")
        if status & 0x01 == 1:
            print("status ok")
        else:
            print("status not ok")
