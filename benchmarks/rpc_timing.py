from math import sqrt

from artiq import *


class RPCTiming(AutoDB):
    __artiq_unit__ = "RPC timing"

    class DBKeys:
        core = Device()
        repeats = Argument(100)
        rpc_time_mean = Result()
        rpc_time_stddev = Result()

    def nop(self, x):
        pass

    @kernel
    def bench(self):
        self.ts = [0.0 for _ in range(self.repeats)]
        for i in range(self.repeats):
            t1 = self.core.get_rtio_time()
            self.nop(10)
            t2 = self.core.get_rtio_time()
            self.ts[i] = float(t2.amount - t1.amount)

    def run(self):
        self.bench()
        mean = sum(self.ts)/self.repeats
        self.rpc_time_stddev = sqrt(
            sum([(t - mean)**2 for t in self.ts]))/self.repeats*s
        self.rpc_time_mean = mean*s
