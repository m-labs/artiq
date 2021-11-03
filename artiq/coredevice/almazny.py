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
        self.mezz_data_high = 0
        self.mezz_data_low = 0

    @kernel
    def reg_enable(self, reg_i):
        self._send_mezz_data([(self.pin_map["REG"][reg_i]["NOE"], 0)])

    @kernel
    def reg_disable(self, reg_i):
        self._send_mezz_data([(self.pin_map["REG"][reg_i]["NOE"], 1)])

    @kernel
    def reg_set(self, reg_i, attin1=0, attin2=0, attin3=0, attin4=0, attin5=0, attin6=0, output_off=1):
        """
        Sets the data on chosen shift register.
        :param reg_i - index of the register [1-4]
        :param attin[1-6] - attenuator input {0, 1}
        :param output_off - RF output off {0, 1}
        """
        # clear the register just in case there was something in there
        self.reg_clear(reg_i)

        shift_reg = [output_off, attin6, attin5, attin4, attin3, attin2, attin1]
        for val in shift_reg:
            self._cycle(reg_i, 
            [(self.pin_map["MOSI"], val),
            (self.pin_map["REG"][reg_i]["NOE"], 1]
            ])

    @kernel
    def reg_clear(self, reg_i):
        """
        Clears content of a register.
        :param reg_i - index of the register [1-4]
        """
        for _ in range(8):
            self._cycle(reg_i, [
                (self.pin_map["REG"][reg_i]["NOE"], 1]),
                (self.pin_map["MOSI"], 0]),
            )

    @kernel
    def reg_clear_all(self):
        """
        Clears all registers.
        Call it whenever it is necessary to change the data.
        """
        # clock low, (not) CLR low
        self._send_mezz_data([
            (self.pin_map["SER_CLK"], 0),
            (self.pin_map["REG_CLEAR", 0]),
        ])
        # clock high, (not) CLR low
        self._send_mezz_data([
            (self.pin_map["SER_CLK"], 1),
            (self.pin_map["REG_CLEAR", 0]),
        ])
        # clock high, (not) CLR high
        self._send_mezz_data([
            (self.pin_map["SER_CLK"], 0),
            (self.pin_map["REG_CLEAR", 1]),
        ])

    @kernel
    def _cycle(self, reg_i, data):
        """
        one cycle for inputting register data
        """
        # keeping reg_clear high all the time anyway
        self._send_mezz_data([
            (self.pin_map["SER_CLK"], 0),
            (self.pin_map["REG_CLEAR"], 1),
            (self.pin_map["REG"][reg_i]["LATCH"], 1),
        ] + data) 
        self._send_mezz_data([
            (self.pin_map["SER_CLK"], 1),
            (self.pin_map["REG_CLEAR"], 1),
            (self.pin_map["REG"][reg_i]["LATCH"], 0),
        ] + data) 

    @kernel
    def _send_mezz_data(self, pins_data)
        """
        Sends the raw data to the mezzanine board.
        :param pins_data - list of tuples in format (pin_number, bit)
        """
        def put_data(w, d):
            if d == 1: # data
                w |= 1 << (pin + 8)
            elif d == 0:
                w &= ~(1 << (pin + 8))
            else:
                raise AttributeError("Data can be only 0 or 1")
            w |= 1 << pin # oe
            return w

        data_low = self.mezz_data_low  # for io pins 0~7
        data_high = self.mezz_data_high  # for io pins 8~15
        for pin, data in pins_data:
            if pin < 8:
                data_low = put_data(data_low, data)
            else:
                data_high = put_data(data_high, data - 8)
        if data_low != self.mezz_data_low: # only send if update is needed
            self.mirny.write_reg(self.mezzio_reg_low, data_low)
            self.mezz_data_low = data_low
        if data_high != self.mezz_data_high:
            self.mirny.write_reg(self.mezzio_reg_high, data_high)
            self.mezz_data_high = data_high
    