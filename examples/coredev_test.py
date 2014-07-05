from artiq.language.experiment import Experiment, kernel
from artiq.devices import corecom_serial, runtime, core, gpio_core

class CompilerTest(Experiment):
	channels = "core led"

	@kernel
	def run(self):
		self.led.set(1)

if __name__ == "__main__":
	coredev = core.Core(runtime.Environment(), corecom_serial.CoreCom())
	exp = CompilerTest(
		core=coredev,
		led=gpio_core.GPIOOut(coredev, 0)
	)
	exp.run()
