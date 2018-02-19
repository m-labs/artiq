import time

from artiq.experiment import *


class _PayloadNOP(EnvExperiment):
    def build(self):
        pass

    def run(self):
        pass


class _PayloadCoreNOP(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        pass


class _PayloadCoreSend100Ints(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def devnull(self, d):
        pass

    @kernel
    def run(self):
        for i in range(100):
            self.devnull(42)


class _PayloadCoreSend1MB(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def devnull(self, d):
        pass

    @kernel
    def run(self):
        data = [0 for _ in range(1000000//4)]
        self.devnull(data)


class _PayloadCorePrimes(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def devnull(self, d):
        pass

    @kernel
    def run(self):
        for x in range(1, 1000):
            d = 2
            prime = True
            while d*d <= x:
                if x % d == 0:
                    prime = False
                    break
                d += 1
            if prime:
                self.devnull(x)


class SpeedBenchmark(EnvExperiment):
    """Speed benchmark"""
    def build(self):
        self.setattr_argument("mode", EnumerationValue(["Single experiment",
                                                        "With pause",
                                                        "With scheduler"]))
        self.setattr_argument("payload", EnumerationValue(["NOP",
                                                           "CoreNOP",
                                                           "CoreSend100Ints",
                                                           "CoreSend1MB",
                                                           "CorePrimes"]))
        self.setattr_argument("nruns", NumberValue(10, min=1, max=1000,
                                                   ndecimals=0, step=1))
        self.setattr_device("core")
        self.setattr_device("scheduler")

    def run_with_scheduler(self):
        nruns = int(self.nruns)

        donop_expid = dict(self.scheduler.expid)
        donop_expid["class_name"] = "_Payload" + self.payload
        donop_expid["arguments"] = {}
        for i in range(nruns):
            self.scheduler.submit(self.scheduler.pipeline_name, donop_expid,
                                  self.scheduler.priority, None, False)

        report_expid = dict(self.scheduler.expid)
        report_expid["class_name"] = "_Report"
        report_expid["arguments"] = {
            "start_time": time.monotonic(),
            "nruns": nruns}
        self.scheduler.submit(self.scheduler.pipeline_name, report_expid,
                              self.scheduler.priority, None, False)

    def run_without_scheduler(self, pause):
        payload = globals()["_Payload" + self.payload](self)

        start_time = time.monotonic()
        for i in range(int(self.nruns)):
            payload.run()
            if pause:
                self.core.comm.close()
                self.scheduler.pause()
        end_time = time.monotonic()

        self.set_dataset("benchmark_run_time",
                         (end_time-start_time)/self.nruns,
                         broadcast=True)

    def run(self):
        if self.mode == "Single experiment":
            self.run_without_scheduler(False)
        elif self.mode == "With pause":
            self.run_without_scheduler(True)
        elif self.mode == "With scheduler":
            self.run_with_scheduler()
        else:
            raise ValueError


class _Report(EnvExperiment):
    def build(self):
        self.setattr_argument("start_time", NumberValue())
        self.setattr_argument("nruns", NumberValue())

    def run(self):
        end_time = time.monotonic()
        self.set_dataset("benchmark_run_time",
                         (end_time-self.start_time)/self.nruns,
                         broadcast=True)
