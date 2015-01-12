from artiq import *
from artiq.coredevice.runtime_exceptions import RTIOUnderflow


def print_min_period(p):
    print("Minimum square wave output period: {} ns".format(p))


class PulsePerformance(AutoDB):
    class DBKeys:
        ttl0 = Device()

    @kernel
    def run(self):
        T = time_to_cycles(100*ns)
        while True:
            try:
                for i in range(1000):
                    self.ttl0.pulse(cycles_to_time(T))
                    delay(cycles_to_time(T))
            except RTIOUnderflow:
                T += 1
                self.core.recover_underflow()
            else:
                print_min_period(int(cycles_to_time(2*T)/(1*ns)))
                break

