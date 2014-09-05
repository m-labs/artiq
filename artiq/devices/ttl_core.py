from artiq.language.core import *


class TTLOut(AutoContext):
    parameters = "channel"

    @kernel
    def pulse(self, duration):
        syscall("rtio_set", now(), self.channel, 1)
        delay(duration)
        syscall("rtio_set", now(), self.channel, 0)
