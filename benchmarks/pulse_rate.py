from artiq import *
from artiq.coredevice.runtime_exceptions import RTIOUnderflow


class PulseRate(AutoDB):
    class DBKeys:
        ttl0 = Device()
        pulse_rate = Result()

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
                self.pulse_rate = cycles_to_time(2*T)
                break
