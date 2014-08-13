from artiq.language.core import *
from artiq.language.units import *

class DDS(AutoContext):
	parameters = "dds_sysclk reg_channel rtio_channel"

	def build(self):
		self._previous_frequency = 0*MHz

	kernel_attr = "_previous_frequency"

	@kernel
	def pulse(self, frequency, duration):
		if self._previous_frequency != frequency:
			syscall("rtio_sync", self.rtio_channel) # wait until output is off
			syscall("dds_program", self.reg_channel,
				(frequency << 2)//(self.dds_sysclk >> 15) << 15)
			self._previous_frequency = frequency
		syscall("rtio_set", now(), self.rtio_channel, 1)
		delay(duration)
		syscall("rtio_set", now(), self.rtio_channel, 0)
