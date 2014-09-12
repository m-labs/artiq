from artiq.language.core import *
from artiq.language.units import *
from artiq.devices import rtio_core


class DDS(AutoContext):
    parameters = "dds_sysclk reg_channel rtio_channel"

    def build(self):
        self.previous_frequency = 0*MHz
        self.sw = rtio_core.RTIOOut(self, channel=self.rtio_channel)

    kernel_attr = "previous_frequency previous_timestamp"

    @kernel
    def on(self, frequency):
        if self.previous_frequency != frequency:
            if self.sw.previous_timestamp != now():
                self.sw.sync()
            if self.sw.previous_value:
                # Channel is already on.
                # Precise timing of frequency change is required.
                fud_time = now()
            else:
                # Channel is off.
                # Use soft timing on FUD to prevent conflicts when
                # reprogramming several channels that need to be turned on at
                # the same time.
                fud_time = -1
            syscall("dds_program", self.reg_channel,
                    int(2**32*frequency/self.dds_sysclk),
                    fud_time)
            self.previous_frequency = frequency
        self.sw.on()

    @kernel
    def off(self):
        self.sw.off()

    @kernel
    def pulse(self, frequency, duration):
        self.on(frequency)
        delay(duration)
        self.off()
