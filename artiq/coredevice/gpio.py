from artiq.language.core import *
from artiq.language.context import *


class GPIOOut(AutoContext):
    channel = Parameter()

    @kernel
    def on(self):
        syscall("gpio_set", self.channel, True)

    @kernel
    def off(self):
        syscall("gpio_set", self.channel, False)
