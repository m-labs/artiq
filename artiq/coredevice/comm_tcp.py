import logging
import socket

from artiq.coredevice.comm_generic import CommGeneric


logger = logging.getLogger(__name__)


class Comm(CommGeneric):
    def __init__(self, dmgr, host, port=1381):
        self.host = host
        self.port = port

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
            rn = self.socket.recv(min(8192, length - len(r)))
            if not rn:
                raise IOError("Connection closed")
            r += rn
        return r

    def write(self, data):
        self.socket.sendall(data)
