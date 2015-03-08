from artiq import *


class SimpleSimulation(Experiment, AutoDB):
    """Simple simulation"""

    class DBKeys:
        core = Device()
        a = Device()
        b = Device()
        c = Device()
        d = Device()

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
    from artiq.sim import devices as sd

    core = sd.Core()
    exp = SimpleSimulation(
        core=core,
        a=sd.WaveOutput(core=core, name="a"),
        b=sd.WaveOutput(core=core, name="b"),
        c=sd.WaveOutput(core=core, name="c"),
        d=sd.WaveOutput(core=core, name="d"),
    )
    exp.run()

if __name__ == "__main__":
    main()
