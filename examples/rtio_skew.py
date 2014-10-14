from artiq import *
from artiq.devices import corecom_serial, core, rtio_core


def print_skew(p):
    print("Input/output skew: {} ns".format(p))


def print_failed():
    print("Pulse was not received back")


class RTIOSkew(AutoContext):
    parameters = "i o"

    @kernel
    def run(self):
        with parallel:
            self.i.gate_rising(10*us)
            with sequential:
                delay(5*us)
                out_t = now()
                self.o.pulse(5*us)
        in_t = self.i.timestamp()
        if in_t < 0*s:
            print_failed()
        else:
            print_skew(int((out_t - in_t)/(1*ns)))

if __name__ == "__main__":
    with corecom_serial.CoreCom() as com:
        coredev = core.Core(com)
        exp = RTIOSkew(core=coredev,
                       i=rtio_core.RTIOIn(core=coredev, channel=0),
                       o=rtio_core.RTIOOut(core=coredev, channel=1))
        exp.run()
