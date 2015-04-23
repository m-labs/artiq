import logging
import socket

from artiq.coredevice.comm_generic import CommGeneric
from artiq.language.db import *


logger = logging.getLogger(__name__)


class Comm(CommGeneric, AutoDB):
    class DBKeys:
        host = Argument()
        port = Argument(1381)

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = socket.create_connection((self.host, self.port))
        logger.debug("connected to host %s on port %d", self.host, self.port)
        self.write(b"ARTIQ coredev\n")

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket
        logger.debug("disconnected")

    def read(self, length):
        r = bytes()
        while len(r) < length:
            r += self.socket.recv(min(8192, length - len(r)))
        return r

    def write(self, data):
        self.socket.sendall(data)
