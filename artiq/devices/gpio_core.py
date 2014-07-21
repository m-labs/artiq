from artiq.language.core import *

class GPIOOut(MPO):
	parameters = "channel"

	@kernel
	def set(self, level):
		syscall("gpio_set", self.channel, level)
