from artiq.experiment import *
import numpy as np
from artiq.coredevice.ad9910 import _AD9910_REG_CFR1

class Test_dds(EnvExperiment):
    """test DDS"""
    def build(self):
        self.setattr_device("core")
        self.setattr_device("urukul0_ch0")
        self.setattr_device("urukul0_cpld")
        
    @rpc
    @staticmethod
    def pr_val(k, v):
        print("{}: 0x{:032x}".format(k, v))

    @kernel
    def run(self):
        self.core.reset()
        delay(100*ms)
    
        cfg_bf = self.urukul0_ch0.read32(_AD9910_REG_CFR1)
        delay(100*ms)
        self.pr_val("cfg before", cfg_bf)
        delay(100*ms)
        self.urukul0_cpld.init()
        delay(100*ms)
        self.urukul0_ch0.init()
        cfg_af = self.urukul0_ch0.read32(_AD9910_REG_CFR1)
        self.pr_val("cfg after", cfg_af)
        delay(100*ms)
        self.urukul0_ch0.sw.on()
        self.urukul0_ch0.set_att(4.0) 
        if cfg_bf == -1:
            self.pr_val("equal to ", -1)
        else:
            self.pr_val("not equal to 0xffff... but", cfg_bf)