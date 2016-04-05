from itertools import count
from time import sleep

from artiq.experiment import *


class RunForever(EnvExperiment):
    def build(self):
        self.setattr_device("scheduler")

    def run(self):
        try:
            for i in count():
                self.scheduler.pause()
                sleep(1)
                print("ping", i)
        except TerminationRequested:
            print("Terminated gracefully")
