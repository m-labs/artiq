from artiq.experiment import *


class TerminateAll(EnvExperiment):
    def build(self):
        self.setattr_device("scheduler")
        self.setattr_argument("graceful_termination", BooleanValue(True))

    def run(self):
        if self.graceful_termination:
            terminate = self.scheduler.request_termination
        else:
            terminate = self.scheduler.delete

        for rid in self.scheduler.get_status().keys():
            if rid != self.scheduler.rid:
                terminate(rid)
