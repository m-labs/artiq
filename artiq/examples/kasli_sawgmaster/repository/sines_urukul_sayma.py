from artiq.experiment import *


class SinesUrukulSayma(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("urukul0_cpld")

        # Urukul clock output syntonized to the RTIO clock.
        # Can be used as HMC830 reference on Sayma RTM.
        # When using this reference, Sayma must be recalibrated every time Urukul
        # is rebooted, as Urukul is not synchronized to the Kasli.
        self.urukul_hmc_ref = self.get_device("urukul0_ch3")

        # Urukul measurement channels - compare with SAWG outputs.
        # When testing sync, do not reboot Urukul, as it is not
        # synchronized to the Kasli.
        self.urukul_meas = [self.get_device("urukul0_ch" + str(i)) for i in range(3)]
        # The same waveform is output on all first 4 SAWG channels (first DAC).
        self.sawgs = [self.get_device("sawg"+str(i)) for i in range(4)]
        self.basemod = self.get_device("basemod_att0")
        self.rfsws = [self.get_device("sawg_sw"+str(i)) for i in range(4)]


    # DRTIO destinations:
    # 0: local
    # 1: Sayma AMC
    # 2: Sayma RTM
    @kernel
    def drtio_is_up(self):
        for i in range(3):
            if not self.core.get_rtio_destination_status(i):
                return False
        return True

    @kernel
    def run(self):
        f = 9*MHz
        dds_ftw = self.urukul_meas[0].frequency_to_ftw(f)
        sawg_ftw = self.sawgs[0].frequency0.to_mu(f)
        if dds_ftw != sawg_ftw:
            print("DDS and SAWG FTWs do not match:", dds_ftw, sawg_ftw)
            return

        self.core.reset()
        self.urukul0_cpld.init()

        delay(1*ms)
        self.urukul_hmc_ref.init()
        self.urukul_hmc_ref.set_mu(0x40000000, asf=self.urukul_hmc_ref.amplitude_to_asf(0.6))
        self.urukul_hmc_ref.set_att(6.)
        self.urukul_hmc_ref.sw.on()

        for urukul_ch in self.urukul_meas:
            delay(1*ms)
            urukul_ch.init()
            urukul_ch.set_mu(dds_ftw, asf=urukul_ch.amplitude_to_asf(0.5))
            urukul_ch.set_att(6.)
            urukul_ch.sw.on()

        while True:
            print("waiting for DRTIO ready...")
            while not self.drtio_is_up():
                pass
            print("OK")

            self.core.reset()

            delay(10*ms)
            self.basemod.reset()
            delay(10*ms)
            self.basemod.set(3.0, 3.0, 3.0, 3.0)
            delay(10*ms)
            for rfsw in self.rfsws:
                delay(1*ms)
                rfsw.on()

            for sawg in self.sawgs:
                delay(1*ms)
                sawg.reset()

            for sawg in self.sawgs:
                delay(1*ms)
                sawg.amplitude1.set(.4)
                sawg.frequency0.set_mu(sawg_ftw)
                sawg.phase0.set_mu(sawg_ftw*now_mu() >> 17)

            while self.drtio_is_up():
                pass
