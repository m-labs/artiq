from artiq import *

import pulse_rate, rtio_skew


_units = [pulse_rate.PulseRate, rtio_skew.RTIOSkew]

class AllBenchmarks(AutoDB):
    def build(self):
        self.se = []
        for unit in _units:
            self.se.append(unit(self.dbh))

    def run(self):
        for se in self.se:
            se.run()
