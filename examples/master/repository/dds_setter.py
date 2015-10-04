from operator import itemgetter

from artiq import *


class DDSSetter(EnvExperiment):
    """DDS Setter"""
    def build(self):
        self.dds = dict()

        ddb = self.get_ddb()
        for k, v in sorted(ddb.items(), key=itemgetter(0)):
            if (isinstance(v, dict)
                    and v["type"] == "local"
                    and v["module"] == "artiq.coredevice.dds"
                    and v["class"] in {"AD9858", "AD9914"}):
                self.dds[k] = {
                    "driver": self.get_device(k),
                    "frequency": self.get_argument("{}_frequency".format(k),
                                                   NumberValue())
                }

    def run(self):
        for k, v in self.dds.items():
            v["driver"].set(v["frequency"])
