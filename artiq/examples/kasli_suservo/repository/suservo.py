from artiq.experiment import *


class SUServo(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led0")
        self.setattr_device("suservo0")
        self.setattr_device("suservo0_ch0")

    def run(self):
        # self.led()
        self.init()

    @kernel
    def init(self):
        self.core.break_realtime()
        self.core.reset()

        self.suservo0.init()
        self.suservo0.set_config(1)
        print(self.suservo0.get_status())
        delay(3*ms)
        self.suservo0.set_config(0)
        delay(3*ms)
        print(self.suservo0.get_status())

    @kernel
    def led(self):
        self.core.break_realtime()
        for i in range(10):
            self.led0.pulse(.1*s)
            delay(.1*s)
