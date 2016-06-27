from time import sleep

from artiq.experiment import *


class CorePause(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("scheduler")

    @kernel
    def k(self):
        print("kernel starting")
        while not self.scheduler.check_pause():
            print("main kernel loop running...")
            sleep(1)
        print("kernel exiting")

    def run(self):
        while True:
            self.k()
            self.scheduler.pause()
