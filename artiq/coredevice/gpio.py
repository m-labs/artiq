from artiq.language.core import *
from artiq.language.db import *


class GPIOOut(AutoDB):
    class DBKeys:
    	core = Device()
        channel = Argument()

    @kernel
    def on(self):
        syscall("gpio_set", self.channel, True)

    @kernel
    def off(self):
        syscall("gpio_set", self.channel, False)
