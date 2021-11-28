from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.zotino import Zotino
from artiq.coredevice.mirny import Mirny as MirnyCPLD
from artiq.coredevice.adf5356 import ADF5356
from artiq.coredevice.urukul import CPLD as UrukulCPLD
from artiq.coredevice.ad9912 import AD9912


@nac3
class NAC3Devices(EnvExperiment):
    core: KernelInvariant[Core]
    zotino0: KernelInvariant[Zotino]
    mirny0_cpld: KernelInvariant[MirnyCPLD]
    mirny0_ch0: KernelInvariant[ADF5356]
    urukul0_cpld: KernelInvariant[UrukulCPLD]
    urukul0_ch0: KernelInvariant[AD9912]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("zotino0")
        self.setattr_device("mirny0_cpld")
        self.setattr_device("mirny0_ch0")
        self.setattr_device("urukul0_cpld")
        self.setattr_device("urukul0_ch0")

    @kernel
    def run(self):
        self.core.reset()
        self.core.delay(1.*ms)
        self.zotino0.init()
        self.zotino0.set_leds(0x15)
        self.core.delay(1.*ms)
        self.zotino0.set_dac([1.2, -5.3, 3.4, 4.5], [0, 1, 2, 3])

        self.core.break_realtime()
        self.core.delay(1.*ms)
        self.mirny0_cpld.init()
        self.mirny0_ch0.init()
        self.mirny0_ch0.set_att_mu(160)
        self.mirny0_ch0.sw.on()
        self.core.break_realtime()
        self.mirny0_ch0.set_frequency(2500.*MHz)

        self.core.break_realtime()
        self.core.delay(1.*ms)
        self.urukul0_cpld.init()
        self.urukul0_ch0.init()
        self.urukul0_ch0.sw.on()
        for i in range(10):
            self.urukul0_ch0.set((10. + float(i))*MHz)
            self.urukul0_ch0.set_att(6.)
            self.core.delay(500.*ms)
