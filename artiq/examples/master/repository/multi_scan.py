from artiq.experiment import *


class MultiScan(EnvExperiment):
    def build(self):
        self.setattr_argument("a", Scannable(default=LinearScan(0, 10, 4)))
        self.setattr_argument("b", Scannable(default=LinearScan(0, 10, 4)))
        self.setattr_argument("c", Scannable(default=LinearScan(0, 10, 4)))

    def run(self):
        msm = MultiScanManager(
            ("a", self.a),
            ("b", self.b),
            ("c", self.c),
        )
        for point in msm:
            print("a={} b={} c={}".format(point.a, point.b, point.c))
