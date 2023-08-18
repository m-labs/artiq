from artiq.experiment import *
from artiq.coredevice.ad9912_reg import *

class SetDDS(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("urukul0_ch0")
        self.setattr_device("urukul0_cpld")
        
    @rpc
    @staticmethod
    def print_sta_reg(sta, reg):
        print("STA: 0x{:x}, AD9912 first reg: 0x{:x}".format(sta, reg))

    @kernel
    def run(self):
        self.core.break_realtime()
        delay(100*ms)
        self.urukul0_cpld.init()

        self.urukul0_ch0.init()

        self.urukul0_ch0.set(125.0*MHz)
        self.urukul0_ch0.set_att(21.0)
        self.urukul0_ch0.cfg_sw(True)
        

    @kernel
    def get_all(self):
        # mostly interested in RF on
        sta = self.urukul0_cpld.sta_read()
        delay(10*ms)
        # get 9912's first register
        fr = self.urukul0_ch0.read(AD9912_SER_CONF, length=1)
        delay(100*ms)
        self.print_sta_reg(sta, fr)
        
    
    @kernel
    @staticmethod
    def is_ad9912_ch_init(channel):
        fr = channel.read(AD9912_SER_CONF, length=1)
        return fr != 0xff

    @kernel
    @staticmethod
    def get_rf_sw(cpld):
        sta = self.urukul0_cpld.sta_read()