from artiq.language.core import *


class GPIOOut(AutoContext):
    parameters = "channel"

    @kernel
    def on(self):
        syscall("gpio_set", self.channel, 1)

    @kernel
    def off(self):
        syscall("gpio_set", self.channel, 0)
