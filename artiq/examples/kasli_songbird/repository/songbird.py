from numpy import int64

from artiq.experiment import *
from artiq.language.core import kernel, compile, KernelInvariant
from artiq.language.units import us, ms, MHz

from artiq.coredevice.songbird import volt_to_mu
from artiq.coredevice.songbird import Songbird as SongbirdConfig, DDS as SongbirdDDS
from artiq.coredevice.core import Core


@compile
class SongbirdExample(EnvExperiment):
    core: KernelInvariant[Core]
    songbird0_config: KernelInvariant[SongbirdConfig]
    songbird0_dds0: KernelInvariant[SongbirdDDS]
    songbird0_dds1: KernelInvariant[SongbirdDDS]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("songbird0_config")
        self.setattr_device("songbird0_dds0")
        self.setattr_device("songbird0_dds1")

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()

        # Remember, LTC2000 requires a 2.4 or 2.5GHz sampling clock.
        # Provide one before starting the example.
        # Clear all DDS channels while configuring them.
        self.songbird0_config.clear(0b1111)
        # Initialize the Songbird DAC with default settings.
        self.songbird0_config.init()
        self.core.delay(1.0*ms)
        
        # Set two waveforms, 50 and 100MHz
        self.songbird0_dds0.set_waveform(
            ampl_offset=volt_to_mu(0.7), 
            damp=0, ddamp=int64(0), dddamp=int64(0),
            phase_offset=0, 
            ftw=self.songbird0_config.frequency_to_mu(50.0*MHz),
            chirp=0,
            shift=0
        )

        self.songbird0_dds1.set_waveform(
            ampl_offset=volt_to_mu(0.25),
            damp=0, ddamp=int64(0), dddamp=int64(0),
            phase_offset=0,
            ftw=self.songbird0_config.frequency_to_mu(100.0*MHz),
            chirp=0,
            shift=0
        )
        self.core.delay(10.0*us)

        # Trigger channels 0 and 1
        self.songbird0_config.trigger(0b0011)
        self.core.delay(1.0*us)
        self.songbird0_config.clear(0b1100)
