from artiq import *
from artiq.coredevice import comm_serial, core, rtio
from artiq.coredevice.runtime_exceptions import RTIOUnderflow


def print_min_period(p):
    print("Minimum square wave output period: {} ns".format(p))


class PulsePerformance(AutoContext):
    parameters = "o"

    @kernel
    def run(self):
        T = time_to_cycles(100*ns)
        while True:
            try:
                for i in range(1000):
                    self.o.pulse(cycles_to_time(T))
                    delay(cycles_to_time(T))
            except RTIOUnderflow:
                T += 1
                delay(1*ms)
            else:
                print_min_period(int(cycles_to_time(2*T)/(1*ns)))
                break


if __name__ == "__main__":
    with comm_serial.Comm() as comm:
        coredev = core.Core(comm)
        exp = PulsePerformance(core=coredev,
                               o=rtio.RTIOOut(core=coredev, channel=1))
        exp.run()
