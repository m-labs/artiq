from artiq import *

import pulse_rate, rtio_skew, rpc_timing

_units = [pulse_rate.PulseRate, rtio_skew.RTIOSkew, rpc_timing.RPCTiming]

class AllBenchmarks(AutoDB):
    __artiq_unit__ = "All benchmarks"

    def build(self):
        self.se = []
        for unit in _units:
            self.se.append(unit(self.dbh))

    def run(self):
        for se in self.se:
            se.run()
