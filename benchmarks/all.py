from artiq import *

import pulse_rate, rtio_skew, rpc_timing


_exps = [pulse_rate.PulseRate, rtio_skew.RTIOSkew, rpc_timing.RPCTiming]

class AllBenchmarks(Experiment, AutoDB):
    """All benchmarks"""

    def build(self):
        self.se = []
        for exp in _exps:
            self.se.append(exp(self.dbh))

    def run(self):
        for se in self.se:
            se.run()
