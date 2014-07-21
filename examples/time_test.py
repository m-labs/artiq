from artiq.language.units import *
from artiq.language.core import *
from artiq.devices import corecom_serial, core

class DummyPulse(MPO):
	parameters = "name"

	def print_on(self, t, f):
		print("{} ON:{:4} @{}".format(self.name, f, t))

	def print_off(self, t):
		print("{}   OFF   @{}".format(self.name, t))

	@kernel
	def pulse(self, f, duration):
		self.print_on(now(), f)
		delay(duration)
		self.print_off(now())

class TimeTest(MPO):
	parameters = "a b c d"

	@kernel
	def run(self):
		i = 0
		while i < 3:
			with parallel:
				with sequential:
					self.a.pulse(100+i, 20*us)
					self.b.pulse(200+i, 20*us)
				with sequential:
					self.c.pulse(300+i, 10*us)
					self.d.pulse(400+i, 20*us)
			i += 1

if __name__ == "__main__":
	with corecom_serial.CoreCom() as com:
		coredev = core.Core(com)
		exp = TimeTest(
			core=coredev,
			a=DummyPulse(core=coredev, name="a"),
			b=DummyPulse(core=coredev, name="b"),
			c=DummyPulse(core=coredev, name="c"),
			d=DummyPulse(core=coredev, name="d"),
		)
		exp.run()
