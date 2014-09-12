from artiq.language.core import *


class RTIOOut(AutoContext):
    parameters = "channel"

    def build(self):
        self.previous_timestamp = int64(0)
        self.previous_value = 0

    kernel_attr = "previous_timestamp previous_value"

    @kernel
    def _set_value(self, value):
        if self.previous_value != value:
            if self.previous_timestamp == now():
                syscall("rtio_replace", now(), self.channel, value)
            else:
                syscall("rtio_set", now(), self.channel, value)
            self.previous_timestamp = now()
            self.previous_value = value

    @kernel
    def sync(self):
        syscall("rtio_sync", self.channel)

    @kernel
    def on(self):
        self._set_value(1)

    @kernel
    def off(self):
        self._set_value(0)

    @kernel
    def pulse(self, duration):
        self.on()
        delay(duration)
        self.off()
