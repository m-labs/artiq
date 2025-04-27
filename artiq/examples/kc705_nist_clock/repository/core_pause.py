from time import sleep

from artiq.experiment import *
from artiq.coredevice.core import Core

# NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/282

@rpc
def sleep_rpc():
    sleep(1)


@compile
class CorePause(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("scheduler")

    @kernel
    def k(self):
        print_rpc("kernel starting")
        while not self.scheduler.check_pause():
            print_rpc("main kernel loop running...")
            sleep_rpc()
        print_rpc("kernel exiting")

    def run(self):
        while True:
            self.k()
            self.scheduler.pause()
