from artiq.language.core import *
from artiq.language.units import *
from artiq.devices import rtio_core


class DDS(AutoContext):
    """Core device Direct Digital Synthesis (DDS) driver.

    This driver controls DDS devices managed directly by the core device's
    runtime. It also uses a RTIO channel (through
    :class:`artiq.devices.rtio_core.RTIOOut`) to control a RF switch that
    gates the output of the DDS device.

    :param dds_sysclk: DDS system frequency, used for computing the frequency
        tuning words.
    :param reg_channel: channel number of the DDS device to control.
    :param rtio_channel: RTIO channel number of the RF switch associated with
        the DDS device.

    """
    parameters = "dds_sysclk reg_channel rtio_channel"

    def build(self):
        self.previous_frequency = 0*MHz
        self.sw = rtio_core.RTIOOut(self, channel=self.rtio_channel)

    kernel_attr = "previous_frequency previous_timestamp"

    @kernel
    def on(self, frequency):
        """Sets the DDS channel to the specified frequency and turns it on.

        If the DDS channel was already on, a real-time frequency update is
        performed.

        """
        if self.previous_frequency != frequency:
            if self.sw.previous_timestamp != now():
                self.sw.sync()
            if self.sw.previous_value:
                # Channel is already on.
                # Precise timing of frequency change is required.
                fud_time = now()
            else:
                # Channel is off.
                # Use soft timing on FUD to prevent conflicts when
                # reprogramming several channels that need to be turned on at
                # the same time.
                fud_time = -1
            syscall("dds_program", self.reg_channel,
                    int(2**32*frequency/self.dds_sysclk),
                    fud_time)
            self.previous_frequency = frequency
        self.sw.on()

    @kernel
    def off(self):
        """Turns the DDS channel off.

        """
        self.sw.off()

    @kernel
    def pulse(self, frequency, duration):
        """Pulses the DDS channel for the specified duration at the specified
        frequency.

        Equivalent to a ``on``, ``delay``, ``off`` sequence.

        """
        self.on(frequency)
        delay(duration)
        self.off()
