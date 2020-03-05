"""RTIO driver for the Fastino 32channel, 16 bit, 2.5 MS/s per channel,
streaming DAC.

TODO: Example, describe update/hold
"""

from artiq.language.core import kernel, portable, delay
from artiq.coredevice.rtio import rtio_output, rtio_output_wide, rtio_input_data
from artiq.language.units import us
from artiq.language.types import TInt32, TList, TFloat


class Fastino:
    """Fastino 32-channel, 16-bit, 2.5 MS/s per channel streaming DAC

    :param channel: RTIO channel number
    :param core_device: Core device name (default: "core")
    :param log2_width: Width of DAC channel group (power of two,
        see the RTIO PHY for details). If zero, the
        :meth:`set_dac`/:meth:`set_dac_mu` interface must be used.
        If non-zero, the :meth:`set_group`/:meth:`set_group_mu`
        interface must be used. Value must match the corresponding value
        in the RTIO PHY.
    """
    kernel_invariants = {"core", "channel", "width"}

    def __init__(self, dmgr, channel, core_device="core", log2_width=0):
        self.channel = channel << 8
        self.core = dmgr.get(core_device)
        self.width = 1 << log2_width

    @kernel
    def init(self):
        """Initialize the device.

        This clears reset, unsets DAC_CLR, enables AFE_PWR,
        clears error counters, then enables error counting
        """
        self.set_cfg(reset=0, afe_power_down=0, dac_clr=0, clr_err=1)
        delay(1*us)
        self.set_cfg(reset=0, afe_power_down=0, dac_clr=0, clr_err=0)
        delay(1*us)

    @kernel
    def write(self, addr, data):
        """Write data to a Fastino register.

        :param addr: Address to write to.
        :param data: Data to write.
        """
        rtio_output(self.channel | addr, data)

    @kernel
    def read(self, addr):
        """Read from Fastino register.

        TODO: untested

        :param addr: Address to read from.
        :return: The data read.
        """
        rtio_output(self.channel | addr | 0x80)
        return rtio_input_data(self.channel >> 8)

    @kernel
    def set_dac_mu(self, dac, data):
        """Write DAC data in machine units.

        :param dac: DAC channel to write to (0-31).
        :param data: DAC word to write, 16 bit unsigned integer, in machine
            units.
        """
        self.write(dac, data)

    @kernel
    def set_group_mu(self, dac: TInt32, data: TList(TInt32)):
        """Write a group of DAC channels in machine units.

        :param dac: First channel in DAC channel group (0-31). The `log2_width`
            LSBs must be zero.
        :param data: List of DAC data pairs (2x16 bit unsigned) to write,
            in machine units. Data exceeding group size is ignored.
            If the list length is less than group size, the remaining
            DAC channels within the group are cleared to 0 (machine units).
        """
        if dac & (self.width - 1):
            raise ValueError("Group index LSBs must be zero")
        rtio_output_wide(self.channel | dac, data)

    @portable
    def voltage_to_mu(self, voltage):
        """Convert SI Volts to DAC machine units.

        :param voltage: Voltage in SI Volts.
        :return: DAC data word in machine units, 16 bit integer.
        """
        return int(round((0x8000/10.)*voltage)) + 0x8000

    @portable
    def voltage_group_to_mu(self, voltage, data):
        """Convert SI Volts to packed DAC channel group machine units.

        :param voltage: List of SI Volt voltages.
        :param data: List of DAC channel data pairs to write to.
            Half the length of `voltage`.
        """
        for i in range(len(voltage)):
            v = self.voltage_to_mu(voltage[i])
            if i & 1:
                v = data[i // 2] | (v << 16)
            data[i // 2] = v

    @kernel
    def set_dac(self, dac, voltage):
        """Set DAC data to given voltage.

        :param dac: DAC channel (0-31).
        :param voltage: Desired output voltage.
        """
        self.write(dac, self.voltage_to_mu(voltage))

    @kernel
    def set_group(self, dac, voltage):
        """Set DAC group data to given voltage.

        :param dac: DAC channel (0-31).
        :param voltage: Desired output voltage.
        """
        data = [int32(0)] * (len(voltage) // 2)
        self.voltage_group_to_mu(voltage, data)
        self.set_group_mu(dac, data)

    @kernel
    def update(self, update):
        """Schedule channels for update.

        :param update: Bit mask of channels to update (32 bit).
        """
        self.write(0x20, update)

    @kernel
    def set_hold(self, hold):
        """Set channels to manual update.

        :param hold: Bit mask of channels to hold (32 bit).
        """
        self.write(0x21, hold)

    @kernel
    def set_cfg(self, reset=0, afe_power_down=0, dac_clr=0, clr_err=0):
        """Set configuration bits.

        :param reset: Reset SPI PLL and SPI clock domain.
        :param afe_power_down: Disable AFE power.
        :param dac_clr: Assert all 32 DAC_CLR signals setting all DACs to
            mid-scale (0 V).
        :param clr_err: Clear error counters and PLL reset indicator.
            This clears the sticky red error LED. Must be cleared to enable
            error counting.
        """
        self.write(0x22, (reset << 0) | (afe_power_down << 1) |
                   (dac_clr << 2) | (clr_err << 3))

    @kernel
    def set_leds(self, leds):
        """Set the green user-defined LEDs

        :param leds: LED status, 8 bit integer each bit corresponding to one
            green LED.
        """
        self.write(0x23, leds)
