import logging
import serial
import struct

from artiq.coredevice.comm_generic import CommGeneric


logger = logging.getLogger(__name__)


class Comm(CommGeneric):
    def __init__(self, dmgr, serial_dev, baud_rate=115200):
        self.serial_dev = serial_dev
        self.baud_rate = baud_rate

    def open(self):
        if hasattr(self, "port"):
            return
        self.port = serial.serial_for_url(self.serial_dev,
                                          baudrate=self.baud_rate)
        self.reset_session()

    def close(self):
        if not hasattr(self, "port"):
            return
        self.port.close()
        del self.port

    def read(self, length):
        r = bytes()
        while len(r) < length:
            r += self.port.read(length - len(r))
        return r

    def write(self, data):
        remaining = len(data)
        pos = 0
        while remaining:
            written = self.port.write(data[pos:])
            remaining -= written
            pos += written
