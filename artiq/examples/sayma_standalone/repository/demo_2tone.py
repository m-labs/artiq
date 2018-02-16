from artiq.experiment import *


class SAWGTestTwoTone(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led0")
        self.setattr_device("ttl_sma_out")

        self.setattr_device("sawg0")
        self.setattr_device("sawg1")
        self.setattr_device("sawg2")
        self.setattr_device("sawg3")

    @kernel
    def run(self):
        self.core.reset()
        delay(1*ms)

        self.sawg0.reset()
        self.sawg1.reset()
        self.sawg2.reset()
        self.sawg3.reset()

        self.sawg0.config.set_clr(1, 1, 1)
        delay(10*us)
        self.sawg0.config.set_out_max(1.)
        delay(10*us)
        self.sawg0.config.set_out_min(-1.)
        delay(10*us)

        while True:
            t_up = t_hold = t_down = 800*ns
            a1 = .3
            a2 = .4
            order = 3

            delay(20*ms)
            self.led0.on()
            self.ttl_sma_out.on()
            self.sawg0.frequency0.set(10*MHz)
            self.sawg0.phase0.set(0.)
            self.sawg0.frequency1.set(1*MHz)
            self.sawg0.phase1.set(0.)
            self.sawg0.frequency2.set(9*MHz)
            self.sawg0.phase2.set(0.)
            with parallel:
                self.sawg0.amplitude1.smooth(.0, a1, t_up, order)
                self.sawg0.amplitude2.smooth(.0, a2, t_up, order)
            self.sawg0.amplitude1.set(a1)
            self.sawg0.amplitude2.set(a2)
            delay(t_hold)
            with parallel:
                self.sawg0.amplitude1.smooth(a1, .0, t_down, order)
                self.sawg0.amplitude2.smooth(a2, .0, t_down, order)
            self.sawg0.amplitude1.set(.0)
            self.sawg0.amplitude2.set(.0)

            self.sawg1.amplitude1.set(.0)
            self.sawg1.amplitude2.set(.0)
            self.ttl_sma_out.off()
            self.led0.off()
