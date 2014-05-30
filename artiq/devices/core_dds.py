from artiq.language.experiment import *
from artiq.language.units import *

class DDS:
	def __init__(self, core, reg_channel, rtio_channel, latency=0*ps, phase_mode="continuous"):
		self.core = core
		self.reg_channel = reg_channel
		self.rtio_channel = rtio_channel
		self.latency = latency
		self.phase_mode = phase_mode

		self._previous_frequency = 0*MHz

	kernel_attr_ro = {"reg_channel", "rtio_channel", "latency", "phase_mode"}
	kernel_attr = {"_previous_frequency"}

	@kernel
	def pulse(self, frequency, duration):
		if self._previous_frequency != frequency:
			self.core.syscall("rtio_sync", self.rtio_channel) # wait until output is off
			self.core.syscall("dds_program", self.reg_channel, frequency)
			self._previous_frequency = frequency
		self.core.syscall("rtio_set", now()-self.latency, self.rtio_channel, 1)
		delay(duration)
		self.core.syscall("rtio_set", now()-self.latency, self.rtio_channel, 0)
