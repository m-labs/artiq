import asyncio
import logging
import socket
import struct
from operator import itemgetter

from quamash import QtGui, QtCore
from pyqtgraph import dockarea

from artiq.tools import TaskObject


logger = logging.getLogger(__name__)


class _TTLWidget(QtGui.QFrame):
    def __init__(self, force_out, name):
        self.force_out = force_out

        QtGui.QFrame.__init__(self)

        self.setFrameShape(QtGui.QFrame.Panel)
        self.setFrameShadow(QtGui.QFrame.Raised)

        grid = QtGui.QGridLayout()
        self.setLayout(grid)
        label = QtGui.QLabel(name)
        label.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(label, 1, 1)

        self._direction = QtGui.QLabel()
        self._value = QtGui.QLabel()
        self._direction.setAlignment(QtCore.Qt.AlignCenter)
        self._value.setAlignment(QtCore.Qt.AlignCenter)
        self.set_value(0, False, False)
        grid.addWidget(self._direction, 2, 1)
        grid.addWidget(self._value, 3, 1, 6, 1)

    def set_value(self, value, oe, override):
        value = "1" if value else "0"
        if override:
            value = "<b>" + value + "</b>"
            color = " color=\"red\""
        else:
            color = ""
        self._value.setText("<font size=\"9\"{}>{}</font>".format(
                            color, value))
        oe = oe or self.force_out
        direction = "OUT" if oe else "IN"
        self._direction.setText("<font size=\"1\">" + direction + "</font>")


class _DeviceManager:
    def __init__(self, init):
        self.ddb = dict()
        self.ttl_cb = lambda: None
        self.ttl_widgets = dict()
        for k, v in init.items():
            self[k] = v

    def __setitem__(self, k, v):
        self.ddb[k] = v
        if k in self.ttl_widgets:
            del self[k]
        if not isinstance(v, dict):
            return
        try:
            if v["type"] == "local" and v["module"] == "artiq.coredevice.ttl":
                channel = v["arguments"]["channel"]
                force_out = v["class"] == "TTLOut"
                self.ttl_widgets[channel] = _TTLWidget(force_out, k)
                self.ttl_cb()
        except KeyError:
            pass

    def __delitem__(self, k):
        del self.ddb[k]
        if k in self.ttl_widgets:
            del self.ttl_widgets[k]
            self.ttl_cb()

    def get_core_addr(self):
        try:
            comm = self.ddb["comm"]
            while isinstance(comm, str):
                comm = self.ddb[comm]
            return comm["arguments"]["host"]
        except KeyError:
            return None


class MonInjTTLDock(dockarea.Dock, TaskObject):
    def __init__(self):
        dockarea.Dock.__init__(self, "TTL", size=(1500, 500))
        self.dm = _DeviceManager(dict())
        self.transport = None

        self.grid = QtGui.QGridLayout()
        gridw = QtGui.QWidget()
        gridw.setLayout(self.grid)
        self.addWidget(gridw)

    @asyncio.coroutine
    def start(self):
        loop = asyncio.get_event_loop()
        yield from loop.create_datagram_endpoint(lambda: self,
                                                 family=socket.AF_INET)
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
        ttl_levels, ttl_oes = struct.unpack(">QQ", data)
        for channel, w in self.dm.ttl_widgets.items():
            w.set_value(ttl_levels & (1 << channel),
                        ttl_oes & (1 << channel),
                        False)

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

    def layout_ttl_widgets(self):
        w = self.grid.itemAt(0)
        while w is not None:
            self.grid.removeItem(w)
            w = self.grid.itemAt(0)
        for i, (_, w) in enumerate(sorted(self.dm.ttl_widgets.items(),
                                   key=itemgetter(0))):
            self.grid.addWidget(w, i // 4, i % 4)

    def init_devices(self, d):
        self.dm = _DeviceManager(d)
        self.dm.ttl_cb = self.layout_ttl_widgets
        self.layout_ttl_widgets()
        return self.dm


class MonInjDDSDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "DDS", size=(1500, 500))

    def init_devices(self, d):
        return d
