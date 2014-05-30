from artiq.language.units import *
from artiq.language.experiment import *

class CompilerTest(Experiment):
	channels = "core a b A B"

	@kernel
	def run():
		for i in range(3):
			with parallel:
				with sequential:
					self.a.pulse(100*MHz, 20*us)
					self.b.pulse(100*MHz, 10*us)
				with sequential:
					self.A.pulse(100*MHz, 10*us)
					self.B.pulse(100*MHz, 10*us)

if __name__ == "__main__":
	from artiq.devices import core, core_dds

	coredev = core.Core()
	exp = CompilerTest(
		core=coredev,
		a=core_dds.DDS(coredev, 0, 0),
		b=core_dds.DDS(coredev, 1, 1),
		A=core_dds.DDS(coredev, 2, 2),
		B=core_dds.DDS(coredev, 3, 3)
	)
	exp.run()
