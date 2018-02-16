from artiq.experiment import *


class UrukulTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("fmcdio_dirctl")
        self.setattr_device("urukul_cpld")
        self.setattr_device("urukul_ch0a")
        self.setattr_device("urukul_ch1a")
        self.setattr_device("urukul_ch2a")
        self.setattr_device("urukul_ch3a")
        self.setattr_device("urukul_ch0b")
        self.setattr_device("urukul_ch1b")
        self.setattr_device("urukul_ch2b")
        self.setattr_device("urukul_ch3b")
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

        self.urukul_cpld.init(clk_sel=0)
        self.urukul_ch0b.init()
        self.urukul_ch1b.init()
        self.urukul_ch2b.init()
        self.urukul_ch3b.init()

        delay(1000*us)
        self.urukul_ch0b.set(100*MHz)
        self.urukul_ch0b.sw.on()
        self.urukul_ch0b.set_att(10.)

        delay(1000*us)
        self.urukul_ch1b.set(10*MHz, 0.5)
        self.urukul_ch1b.sw.on()
        self.urukul_ch1b.set_att(0.)

        delay(1000*us)
        self.urukul_ch2b.set(400*MHz)
        self.urukul_ch2b.sw.on()
        self.urukul_ch2b.set_att(0.)

        delay(1000*us)
        self.urukul_ch3b.set(1*MHz)
        self.urukul_ch3b.sw.on()
        self.urukul_ch3b.set_att(20.)

        i = 0
        j = 0
        while True:
            delay(13*us)
            self.urukul_ch0b.write32(0x07, i)
            self.urukul_cpld.io_update.pulse(10*ns)
            k = self.urukul_ch0b.read32(0x07)
            delay(100*us)
            if k != i:
                #print(i)
                #print(k)
                #if j > 20:
                #    return
                j += 1
                #delay(20*ms)
            i += 1

        while True:
            self.urukul_ch0b.sw.pulse(5*ms)
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
