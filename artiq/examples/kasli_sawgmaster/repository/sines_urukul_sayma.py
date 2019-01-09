from artiq.experiment import *


class SinesUrukulSayma(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("urukul0_cpld")
        self.urukul_chs = [self.get_device("urukul0_ch" + str(i)) for i in range(4)]
        self.sawgs = [self.get_device("sawg"+str(i)) for i in range(8)]

    @kernel
    def drtio_is_up(self):
        for i in range(2):
            if not self.core.get_rtio_destination_status(i):
                return False
        return True

    @kernel
    def run(self):
        # Note: when testing sync, do not reboot Urukul, as it is not
        # synchronized to the FPGA (yet).
        self.core.reset()
        self.urukul0_cpld.init()
        for urukul_ch in self.urukul_chs:
            delay(1*ms)
            urukul_ch.init()
            urukul_ch.set(9*MHz, amplitude=0.5)
            urukul_ch.set_att(6.)
            urukul_ch.sw.on()

        while True:
            print("waiting for DRTIO ready...")
            while not self.drtio_is_up():
                pass
            print("OK")

            self.core.reset()

            for sawg in self.sawgs:
                delay(1*ms)
                sawg.reset()

            for sawg in self.sawgs:
                delay(1*ms)
                sawg.amplitude1.set(.4)
                sawg.frequency0.set(9*MHz)

            while self.drtio_is_up():
                pass
