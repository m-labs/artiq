from artiq import *


def print_failed():
    print("Pulse was not received back")


class RTIOSkew(AutoDB):
    class DBKeys:
        pmt0 = Device()
        ttl0 = Device()
        io_skew = Result()

    @kernel
    def run(self):
        with parallel:
            self.pmt0.gate_rising(10*us)
            with sequential:
                delay(5*us)
                out_t = now()
                self.ttl0.pulse(5*us)
        in_t = self.pmt0.timestamp()
        if in_t < 0*s:
            print_failed()
        else:
            self.io_skew = out_t - in_t
