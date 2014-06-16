from artiq.language.units import *
from artiq.language.experiment import *

my_range = range

class CompilerTest(Experiment):
	channels = "core a b A B"

	def print_done(self):
		print("Done!")

	def print_iter(self, n):
		print("Iteration: {}".format(n))

	@kernel
	def run(self, n, t2):
		t2 += 1*us
		for i in my_range(n):
			self.print_iter(i)
			with parallel:
				with sequential:
					self.a.pulse(100*MHz, 20*us)
					self.b.pulse(100*MHz, t2)
				with sequential:
					self.A.pulse(100*MHz, 10*us)
					self.B.pulse(100*MHz, t2)
		self.print_done()

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
	exp.run(3, 100*us)
