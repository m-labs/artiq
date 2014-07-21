from artiq.language.units import *
from artiq.language.core import *
from artiq.devices import corecom_serial, core, ttl_core

class TTLTest(MPO):
	parameters = "a b c d"

	@kernel
	def run(self):
		delay(10*us)
		i = 0
		while i < 100000:
			with parallel:
				with sequential:
					self.a.pulse(50*us)
					self.b.pulse(50*us)
				with sequential:
					self.c.pulse(10*us)
					self.d.pulse(20*us)
			i += 1

if __name__ == "__main__":
	with corecom_serial.CoreCom() as com:
		coredev = core.Core(com)
		exp = TTLTest(
			core=coredev,
			a=ttl_core.TTLOut(core=coredev, channel=0),
			b=ttl_core.TTLOut(core=coredev, channel=1),
			c=ttl_core.TTLOut(core=coredev, channel=2),
			d=ttl_core.TTLOut(core=coredev, channel=3),
		)
		exp.run()
