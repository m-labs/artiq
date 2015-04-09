import logging
import serial
import struct

from artiq.coredevice.comm_generic import CommGeneric
from artiq.language.db import *


logger = logging.getLogger(__name__)


class Comm(CommGeneric, AutoDB):
    class DBKeys:
        serial_dev = Parameter()
        baud_rate = Parameter(115200)

    def open(self):
        if hasattr(self, "port"):
            return
        self.port = serial.serial_for_url(self.serial_dev, baudrate=115200)
        self.port.flush()
        self.set_remote_baud(self.baud_rate)
        self.set_baud(self.baud_rate)

    def close(self):
        if not hasattr(self, "port"):
            return
        self.set_remote_baud(115200)
        self.port.close()
        del self.port

    def read(self, length):
        r = bytes()
        while(len(r) < length):
            r += self.port.read(length - len(r))
        return r

    def write(self, data):
        remaining = len(data)
        pos = 0
        while remaining:
            written = self.port.write(data[pos:])
            remaining -= written
            pos += written

    def set_baud(self, baud):
        self.port.baudrate = baud
        self.port.flush()
        logger.debug("local baud rate set to %d", baud)

    def set_remote_baud(self, baud):
        self.send_link_message(struct.pack(">l", baud))
        handshake = 0
        fails = 0
        while handshake < 4:
            (recv, ) = struct.unpack("B", self.read(1))
            if recv == 0x5a:
                handshake += 1
            else:
                # FIXME: when loading immediately after a board reset,
                # we erroneously get some zeros back.
                logger.warning("unexpected sync character: %02x", recv)
                handshake = 0
                if recv != 0:
                    fails += 1
                    if fails > 3:
                        raise IOError("Baudrate ack failed")
        logger.debug("remote baud rate set to %d", baud)
