from artiq.language.core import *
from artiq.language.units import *


class DDS(AutoContext):
    parameters = "dds_sysclk reg_channel rtio_channel"

    def build(self):
        self._previous_frequency = 0*MHz

    kernel_attr = "_previous_frequency"

    @kernel
    def _set_frequency(self, frequency):
        if self._previous_frequency != frequency:
            syscall("rtio_sync", self.rtio_channel)  # wait until output is off
            syscall("dds_program", self.reg_channel,
                    int(2**32*frequency/self.dds_sysclk))
            self._previous_frequency = frequency

    @kernel
    def pulse(self, frequency, duration):
        self._set_frequency(frequency)
        syscall("rtio_set", now(), self.rtio_channel, 1)
        delay(duration)
        syscall("rtio_set", now(), self.rtio_channel, 0)

    @kernel
    def on(self, frequency):
        self._set_frequency(frequency)
        syscall("rtio_set", now(), self.rtio_channel, 1)

    @kernel
    def off(self):
        syscall("rtio_set", now(), self.rtio_channel, 0)
