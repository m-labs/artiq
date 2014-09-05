from artiq.language.core import *


class GPIOOut(AutoContext):
    parameters = "channel"

    @kernel
    def set(self, level):
        syscall("gpio_set", self.channel, level)
