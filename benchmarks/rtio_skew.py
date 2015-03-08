from artiq import *


class PulseNotReceived(Exception):
    pass


class RTIOSkew(AutoDB):
    __artiq_unit__ = "RTIO skew"

    class DBKeys:
        core = Device()
        pmt0 = Device()
        ttl0 = Device()
        rtio_skew = Result()

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
            raise PulseNotReceived
        self.rtio_skew = out_t - in_t
