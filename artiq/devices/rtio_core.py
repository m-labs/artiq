from artiq.language.core import *


class _RTIOBase(AutoContext):
    parameters = "channel"

    def build(self):
        self.previous_timestamp = int64(0)
        self.previous_value = 0

    kernel_attr = "previous_timestamp previous_value"

    @kernel
    def _set_oe(self, oe):
        syscall("rtio_oe", self.channel, oe)

    @kernel
    def _set_value(self, value):
        if self.previous_value != value:
            if self.previous_timestamp == now():
                syscall("rtio_replace", now(), self.channel, value)
            else:
                syscall("rtio_set", now(), self.channel, value)
            self.previous_timestamp = now()
            self.previous_value = value


class RTIOOut(_RTIOBase):
    def build(self):
        _RTIOBase.build(self)
        self._set_oe(1)

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


class RTIOCounter(_RTIOBase):
    def build(self):
        _RTIOBase.build(self)
        self._set_oe(0)

    @kernel
    def count_rising(self, duration):
        self._set_value(1)
        delay(duration)
        self._set_value(0)

    @kernel
    def count_falling(self, duration):
        self._set_value(2)
        delay(duration)
        self._set_value(0)

    @kernel
    def count_both_edges(self, duration):
        self._set_value(3)
        delay(duration)
        self._set_value(0)

    @kernel
    def sync(self):
        count = 0
        while syscall("rtio_get", self.channel) >= 0:
            count += 1
        return count
