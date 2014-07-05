from artiq.language.experiment import *

class GPIOOut:
	def __init__(self, core, channel=0):
		self.core = core
		self.channel = channel

	kernel_attr_ro = "channel"

	@kernel
	def set(self, level):
		syscall("gpio_set", self.channel, level)
