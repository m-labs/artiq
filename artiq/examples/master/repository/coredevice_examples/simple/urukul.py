from artiq.experiment import *


class UrukulTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("fmcdio_dirctl")
        self.setattr_device("urukul_cpld")
        self.setattr_device("urukul_ch0")
        self.setattr_device("urukul_ch1")
        self.setattr_device("urukul_ch2")
        self.setattr_device("urukul_ch3")
        self.setattr_device("led")

    def p(self, f, *a):
        print(f % a)

    @kernel
    def run(self):
        self.core.reset()
        self.led.on()
        delay(5*ms)
        # Zotino plus Urukul (MISO, IO_UPDATE_RET)
        self.fmcdio_dirctl.set(0x0A008800)
        self.led.off()

        self.urukul_cpld.init(clk_sel=1)
        self.urukul_ch0.init()
        self.urukul_ch1.init()
        self.urukul_ch2.init()
        self.urukul_ch3.init()
        delay(100*us)

        self.urukul_ch0.set(10*MHz)
        self.urukul_ch0.sw.on()
        self.urukul_ch0.set_att(10.)

        delay(100*us)
        self.urukul_ch1.set(10*MHz, 0.5)
        self.urukul_ch1.sw.on()
        self.urukul_ch1.set_att(10.)

        delay(100*us)
        self.urukul_ch2.set(400*MHz)
        self.urukul_ch2.sw.on()
        self.urukul_ch2.set_att(0.)

        delay(100*us)
        self.urukul_ch3.set(1*MHz)
        self.urukul_ch3.sw.on()
        self.urukul_ch3.set_att(0.)

        while True:
            self.urukul_ch0.set_mu(0x123456789abc, 0)

        while True:
            self.urukul_ch0.sw.pulse(5*ms)
            delay(5*ms)

        while False:
            self.led.pulse(.5*s)
            delay(.5*s)

    @kernel
    def test_att_noise(self, n=1024):
        bus = self.urukul_cpld.bus
        bus.set_config_mu(_SPI_CONFIG, _SPIT_ATT_WR, _SPIT_ATT_RD)
        bus.set_xfer(CS_ATT, 32, 0)
        for i in range(n):
            delay(5*us)
            bus.write(self.att_reg)
        bus.set_config_mu(_SPI_CONFIG, _SPIT_DDS_WR, _SPIT_DDS_RD)
