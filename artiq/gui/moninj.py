import asyncio
import logging
import socket
import struct

from quamash import QtGui
from pyqtgraph import dockarea

from artiq.tools import TaskObject


logger = logging.getLogger(__name__)


class _DeviceManager:
    def __init__(self, init):
        self.comm = None
        if "comm" in init:
            self.comm = init["comm"]

    def __setitem__(self, k, v):
        if k == "comm":
            self.comm = v

    def get_core_addr(self):
        if self.comm is None:
            return None
        try:
            return self.comm["arguments"]["host"]
        except KeyError:
            return None


class MonInjTTLDock(dockarea.Dock, TaskObject):
    def __init__(self):
        dockarea.Dock.__init__(self, "TTL", size=(1500, 500))
        self.dm = _DeviceManager(dict())
        self.transport = None

    @asyncio.coroutine
    def start(self):
        loop = asyncio.get_event_loop()
        yield from loop.create_datagram_endpoint(lambda: self, family=socket.AF_INET)
        TaskObject.start(self)

    @asyncio.coroutine
    def stop(self):
        yield from TaskObject.stop(self)
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        levels, oe = struct.unpack(">QQ", data)
        print("Received:", hex(levels), hex(oe))

    def error_received(self, exc):
        logger.warning("datagram endpoint error")

    def connection_lost(self, exc):
        self.transport = None

    @asyncio.coroutine
    def _do(self):
        while True:
            yield from asyncio.sleep(0.2)
            ca = self.dm.get_core_addr()
            if ca is None:
                logger.warning("could not find core device address")
            elif self.transport is None:
                logger.warning("datagram endpoint not available")
            else:
                # MONINJ_REQ_MONITOR
                self.transport.sendto(b"\x01", (ca, 3250))

    def init_devices(self, d):
        self.dm = _DeviceManager(d)
        return self.dm


class MonInjDDSDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "DDS", size=(1500, 500))

    def init_devices(self, d):
        return d
