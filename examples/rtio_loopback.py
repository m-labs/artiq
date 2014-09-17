from artiq.language.core import *
from artiq.language.units import *
from artiq.devices import corecom_serial, core, rtio_core


class RTIOLoopback(AutoContext):
    parameters = "i o"

    def report(self, n):
        print(n)

    @kernel
    def run(self):
        with parallel:
            with sequential:
                for i in range(4):
                    delay(25*ns)
                    self.o.pulse(25*ns)
            self.i.count_rising(1*us)
        self.report(self.i.sync())


if __name__ == "__main__":
    with corecom_serial.CoreCom() as com:
        coredev = core.Core(com)
        exp = RTIOLoopback(
            core=coredev,
            i=rtio_core.RTIOCounter(core=coredev, channel=0),
            o=rtio_core.RTIOOut(core=coredev, channel=1)
        )
        exp.run()
