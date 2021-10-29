"""RTIO driver for Almazny (Mirny mezzanine board)
"""

from artiq.language.core import kernel, delay
from artiq.language.units import us

class Almazny
    """
    Almazny

    :param mirny - Mirny device object to communicate to Almazny through
    """

    # Mezz_IO pin map
    pin_map = {
        "SER_MOSI": 8,
        "SER_CLK": 5,
        "REG": {
            # REG 1
            1: { "NOE": 9, "LATCH": 10 }
            # REG 2
            2: { "NOE": 12, "LATCH": 13 }
            # REG 3
            3: { "NOE": 14, "LATCH": 15 }
            # REG 4
            4: { "NOE": 0, "LATCH": 1 }
        },
        "REG_CLEAR": 3
    }

    mezzio_reg_low = 0x3 # register addr for Mezz_IO 0~7
    mezzio_reg_high = 0xC # register addr for Mezz_IO 8~15

    def __init__(self, mirny):
        self.mirny = mirny

    @kernel
    def set_reg(self, reg_i, attin1, attin2, attin3, attin4, attin5, attin6):
        """
        Sets the data on chosen shift register.
        """
        pass

    @kernel
    def _send_mezz_data(self, pins_data)
        """
        Sends the raw data to the mezzanine board.
        :param pins_data - list of tuples in format (pin_number, bit)
        """
        mezz_data_low = 0  # for io pins 0~7
        mezz_data_high = 0  # for io pins 8~15
        for pin, data in pins_data:
            if pin < 8:
                mezz_data_low |= data << (pin + 8)  # data
                mezz_data_low |= 1 << pin  # oe
            else:
                mezz_data_high |= data << pin
                mezz_data_high |= 1 << (pin - 8)
        if mezz_io_low != 0:
            self.mirny.write_reg(self.mezzio_reg_low, mezz_data_low)
        if mezz_io_high != 0:
            self.mirny.write_reg(self.mezzio_reg_high, mezz_data_high)
    