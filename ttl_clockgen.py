from artiq.experiment import *

class ClockGeneratorLoopback(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_clock_in")
        self.setattr_device("loop_clock_out")

    @kernel
    def run(self):
        self.core.reset()
        # self.loop_clock_in.input()
        # # self.loop_clock_out.stop()
        # delay(200*us)
        # with parallel:
        #     self.loop_clock_in.gate_rising(10*us)
        #     with sequential:
        #         delay(200*ns)
        self.loop_clock_out.set(1*MHz)
        delay(20*s)
        self.loop_clock_out.stop()
