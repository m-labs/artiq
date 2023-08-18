from artiq.experiment import *

# This is a volatile test script to exercise and evaluate some functionality of
# Phaser through ARTIQ.


class Phaser(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("phaser0")

    @rpc(flags={"async"})
    def p(self, *p):
        print([hex(_ & 0xFFFFFFFF) for _ in p])

    def run(self):
        self.do()

    @kernel
    def do(self):
        # self.core.reset()
        self.core.break_realtime()
        for i in range(1):
            self.inner()

    @kernel
    def inner(self):
        f = self.phaser0

        f.init(debug=True)

        for ch in range(2):
            f.channel[ch].set_att(0 * dB)
            # f.channel[ch].set_duc_frequency_mu(0)
            f.channel[ch].set_duc_frequency(190.598551 * MHz)
            f.channel[ch].set_duc_phase(0.25)
            f.channel[ch].set_duc_cfg(select=0, clr=0)
            delay(0.1 * ms)
            for osc in range(5):
                ftw = (osc + 1) * 1.875391 * MHz
                asf = (osc + 1) * 0.066
                # if osc != 4:
                #    asf = 0.
                # else:
                #    asf = .9
                #    ftw = 9.5*MHz
                # f.channel[ch].oscillator[osc].set_frequency_mu(0)
                f.channel[ch].oscillator[osc].set_frequency(ftw)
                delay(0.1 * ms)
                f.channel[ch].oscillator[osc].set_amplitude_phase(
                    asf, phase=0.25, clr=0
                )
                delay(0.1 * ms)
        f.duc_stb()

        for ch in range(2):
            for addr in range(8):
                r = f.channel[ch].trf_read(addr)
                delay(0.1 * ms)
                self.p(r)
                self.core.break_realtime()

        alarm = f.dac_read(0x05)
        self.p(alarm)
        self.core.break_realtime()
        # This will set the TRFs and the DAC to sleep.
        # Saves power and temperature rise but oviously disables RF as
        # well.
        # f.set_cfg(dac_sleep=1, trf0_ps=1, trf1_ps=1)
        #self.core.wait_until_mu(now_mu())
