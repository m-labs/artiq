from artiq.language.core import AutoContext, kernel
from artiq.devices import corecom_serial, core, gpio_core

class CompilerTest(AutoContext):
	parameters = "led"

	def output(self, n):
		print("Received: "+str(n))

	def get_max(self):
		return int(input("Maximum: "))

	@kernel
	def run(self):
		self.led.set(1)
		x = 1
		m = self.get_max()
		while x < m:
			d = 2
			prime = 1
			while d*d <= x:
				if x % d == 0:
					prime = 0
				d = d + 1
			if prime == 1:
				self.output(x)
			x = x + 1
		self.led.set(0)

if __name__ == "__main__":
	with corecom_serial.CoreCom() as com:
		coredev = core.Core(com)
		exp = CompilerTest(
			core=coredev,
			led=gpio_core.GPIOOut(core=coredev, channel=0)
		)
		exp.run()
