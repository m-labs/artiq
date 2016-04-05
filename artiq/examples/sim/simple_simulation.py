from artiq.experiment import *


class SimpleSimulation(EnvExperiment):
    """Simple simulation"""

    def build(self):
        self.setattr_device("core")
        for wo in "abcd":
            self.setattr_device(wo)

    @kernel
    def run(self):
        with parallel:
            with sequential:
                self.a.pulse(100*MHz, 20*us)
                self.b.pulse(200*MHz, 20*us)
            with sequential:
                self.c.pulse(300*MHz, 10*us)
                self.d.pulse(400*MHz, 20*us)


def main():
    from artiq.sim import devices

    dmgr = dict()
    dmgr["core"] = devices.Core(dmgr)
    for wo in "abcd":
        dmgr[wo] = devices.WaveOutput(dmgr, wo)
    exp = SimpleSimulation(dmgr)
    exp.run()

if __name__ == "__main__":
    main()
