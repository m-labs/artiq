from artiq.language.units import *
from artiq.language.core import *

class SimpleSimulation(MPO):
	channels = "a b c d"

	@kernel
	def run(self):
		with parallel:
			with sequential:
				self.a.pulse(100*MHz, 20*us)
				self.b.pulse(200*MHz, 20*us)
			with sequential:
				self.c.pulse(300*MHz, 10*us)
				self.d.pulse(400*MHz, 20*us)

if __name__ == "__main__":
	from artiq.sim import devices as sd
	from artiq.sim import time

	exp = SimpleSimulation(
		core=sd.Core(),
		a=sd.WaveOutput("a"),
		b=sd.WaveOutput("b"),
		c=sd.WaveOutput("c"),
		d=sd.WaveOutput("d"),
	)
	exp.run()
	print(time.manager.format_timeline())
