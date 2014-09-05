from artiq.language.units import *
from artiq.language.core import *


my_range = range


class CompilerTest(AutoContext):
    parameters = "a b A B"

    def print_done(self):
        print("Done!")

    def set_some_slowdev(self, n):
        print("Slow device setting: {}".format(n))

    @kernel
    def run(self, n, t2):
        for i in my_range(n):
            self.set_some_slowdev(i)
            delay(100*ms)
            with parallel:
                with sequential:
                    for j in my_range(3):
                        self.a.pulse((j+1)*100*MHz, 20*us)
                        self.b.pulse(100*MHz, t2)
                with sequential:
                    self.A.pulse(100*MHz, 10*us)
                    self.B.pulse(100*MHz, t2)
        self.print_done()


if __name__ == "__main__":
    from artiq.devices import corecom_dummy, core, dds_core

    coredev = core.Core(corecom_dummy.CoreCom())
    exp = CompilerTest(
        core=coredev,
        a=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                       reg_channel=0, rtio_channel=0),
        b=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                       reg_channel=1, rtio_channel=1),
        A=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                       reg_channel=2, rtio_channel=2),
        B=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                       reg_channel=3, rtio_channel=3)
    )
    exp.run(3, 100*us)
