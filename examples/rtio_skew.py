from artiq import *


class PulseNotReceived(Exception):
    pass


class RTIOSkew(AutoDB):
    class DBKeys:
        pmt0 = Device()
        ttl0 = Device()
        io_skew = Result()

    @staticmethod
    def realtime_results():
        return {
            "io_skew": "raw"
        }

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
        self.io_skew = out_t - in_t
