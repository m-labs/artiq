# Copyright 2013-2017 Robert Jordens <jordens@gmail.com>
#
# This file is part of pdq.
#
# pdq is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pdq is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pdq.  If not, see <http://www.gnu.org/licenses/>.

from math import log, sqrt
import logging
import struct

import serial

from artiq.wavesynth.coefficients import discrete_compensate
from artiq.language.core import kernel, portable, delay_mu

from .crc import CRC
from .protocol import PDQBase, PDQ_CMD


logger = logging.getLogger(__name__)

crc8 = CRC(0x107)


class PDQ(PDQBase):
    def __init__(self, url=None, dev=None, **kwargs):
        """Initialize PDQ USB/Parallel device stack.

        .. note:: This device should only be used if the PDQ is intended to be
           configured using the USB connection and **not** via SPI.

        Args:
            url (str): Pyserial device URL. Can be ``hwgrep://`` style
                (search for serial number, bus topology, USB VID:PID
                combination), ``COM15`` for a Windows COM port number,
                ``/dev/ttyUSB0`` for a Linux serial port.
            dev (file-like): File handle to use as device. If passed, ``url``
                is ignored.
            **kwargs: See :class:`PDQBase` .
        """
        if dev is None:
            dev = serial.serial_for_url(url)
        self.dev = dev
        self.crc = 0
        PDQBase.__init__(self, **kwargs)

    def write(self, data):
        """Write data to the PDQ board over USB/parallel.

        SOF/EOF control sequences are appended/prepended to
        the (escaped) data. The running checksum is updated.

        Args:
            data (bytes): Data to write.
        """
        logger.debug("> %r", data)
        msg = b"\xa5\x02" + data.replace(b"\xa5", b"\xa5\xa5") + b"\xa5\x03"
        written = self.dev.write(msg)
        if isinstance(written, int):
            assert written == len(msg), (written, len(msg))
        self.crc = crc8(data, self.crc)

    def write_reg(self, adr, data, board):
        """Write to a configuration register.

        Args:
            board (int): Board to write to (0-0xe), 0xf for all boards.
            adr (int): Register address to write to (0-3).
            data (int): Data to write (1 byte)
        """
        self.write(struct.pack(
            "<BB", PDQ_CMD(board, False, adr, True), data))

    def write_mem(self, channel, data, start_addr=0):
        """Write to channel memory.

        Args:
            channel (int): Channel index to write to. Assumes every board in
                the stack has :attr:`num_dacs` DAC outputs.
            data (bytes): Data to write to memory.
            start_addr (int): Start address to write data to.
        """
        board, dac = divmod(channel, self.num_dacs)
        self.write(struct.pack("<BH", PDQ_CMD(board, True, dac, True),
                               start_addr) + data)

    def close(self):
        """Close the USB device handle."""
        self.dev.close()
        del self.dev

    def flush(self):
        """Flush pending data."""
        self.dev.flush()
