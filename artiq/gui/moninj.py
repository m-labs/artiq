import asyncio
import logging
import socket
import struct
from operator import itemgetter

from quamash import QtGui, QtCore
from pyqtgraph import dockarea

from artiq.tools import TaskObject
from artiq.protocols.sync_struct import Subscriber


logger = logging.getLogger(__name__)


_mode_enc = {
    "exp": 0,
    "1": 1,
    "0": 2,
    "in": 3
}


class _TTLWidget(QtGui.QFrame):
    def __init__(self, channel, send_to_device, force_out, title):
        self.channel = channel
        self.send_to_device = send_to_device
        self.force_out = force_out

        QtGui.QFrame.__init__(self)

        self.setFrameShape(QtGui.QFrame.Panel)
        self.setFrameShadow(QtGui.QFrame.Raised)

        grid = QtGui.QGridLayout()
        self.setLayout(grid)
        label = QtGui.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        grid.addWidget(label, 1, 1)

        self._direction = QtGui.QLabel()
        self._direction.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self._direction, 2, 1)
        self._override = QtGui.QLabel()
        self._override.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self._override, 3, 1)
        self._value = QtGui.QLabel()
        self._value.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self._value, 4, 1, 6, 1)

        self._value.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        menu = QtGui.QActionGroup(self._value)
        menu.setExclusive(True)
        self._expctl_action = QtGui.QAction("Experiment controlled", self._value)
        self._expctl_action.setCheckable(True)
        menu.addAction(self._expctl_action)
        self._value.addAction(self._expctl_action)
        self._expctl_action.triggered.connect(lambda: self.set_mode("exp"))
        separator = QtGui.QAction(self._value)
        separator.setSeparator(True)
        self._value.addAction(separator)
        self._force1_action = QtGui.QAction("Force 1", self._value)
        self._force1_action.setCheckable(True)
        menu.addAction(self._force1_action)
        self._value.addAction(self._force1_action)
        self._force1_action.triggered.connect(lambda: self.set_mode("1"))
        self._force0_action = QtGui.QAction("Force 0", self._value)
        self._force0_action.setCheckable(True)
        menu.addAction(self._force0_action)
        self._value.addAction(self._force0_action)
        self._force0_action.triggered.connect(lambda: self.set_mode("0"))
        self._forcein_action = QtGui.QAction("Force input", self._value)
        self._forcein_action.setCheckable(True)
        self._forcein_action.setEnabled(not force_out)
        menu.addAction(self._forcein_action)
        self._value.addAction(self._forcein_action)
        self._forcein_action.triggered.connect(lambda: self.set_mode("in"))

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 0)
        grid.setRowStretch(4, 0)
        grid.setRowStretch(5, 1)

        self.set_value(0, False, False)

    def set_mode(self, mode):
        data = struct.pack("bbb",
                           2,  # MONINJ_REQ_TTLSET
                           self.channel, _mode_enc[mode])
        self.send_to_device(data)

    def set_value(self, value, oe, override):
        value_s = "1" if value else "0"
        if override:
            value_s = "<b>" + value_s + "</b>"
            color = " color=\"red\""
            self._override.setText("<font size=\"1\" color=\"red\">OVERRIDE</font>")
        else:
            color = ""
            self._override.setText("")
        self._value.setText("<font size=\"9\"{}>{}</font>".format(
                            color, value_s))
        oe = oe or self.force_out
        direction = "OUT" if oe else "IN"
        self._direction.setText("<font size=\"1\">" + direction + "</font>")
        if override:
            if oe:
                if value:
                    self._force1_action.setChecked(True)
                else:
                    self._force0_action.setChecked(True)
            else:
                self._forcein_action.setChecked(True)
        else:
            self._expctl_action.setChecked(True)


class _DDSWidget(QtGui.QFrame):
    def __init__(self, channel, sysclk, title):
        self.channel = channel
        self.sysclk = sysclk

        QtGui.QFrame.__init__(self)

        self.setFrameShape(QtGui.QFrame.Panel)
        self.setFrameShadow(QtGui.QFrame.Raised)

        grid = QtGui.QGridLayout()
        self.setLayout(grid)
        label = QtGui.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        grid.addWidget(label, 1, 1)

        self._value = QtGui.QLabel()
        self._value.setAlignment(QtCore.Qt.AlignCenter)
        self._value.setWordWrap(True)
        grid.addWidget(self._value, 2, 1, 6, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 1)

        self.set_value(0)

    def set_value(self, ftw):
        frequency = ftw*self.sysclk/2**32
        self._value.setText("<font size=\"6\">{:.7f} MHz</font>"
                            .format(float(frequency)/1e6))


class _DeviceManager:
    def __init__(self, send_to_device, init):
        self.send_to_device = send_to_device
        self.ddb = dict()
        self.ttl_cb = lambda: None
        self.ttl_widgets = dict()
        self.dds_cb = lambda: None
        self.dds_widgets = dict()
        for k, v in init.items():
            self[k] = v

    def __setitem__(self, k, v):
        if k in self.ttl_widgets:
            del self[k]
        if k in self.dds_widgets:
            del self[k]
        self.ddb[k] = v
        if not isinstance(v, dict):
            return
        try:
            if v["type"] == "local":
                title = k
                if "comment" in v:
                    title += ": " + v["comment"]
                if v["module"] == "artiq.coredevice.ttl":
                    channel = v["arguments"]["channel"]
                    force_out = v["class"] == "TTLOut"
                    self.ttl_widgets[k] = _TTLWidget(
                        channel, self.send_to_device, force_out, title)
                    self.ttl_cb()
                if (v["module"] == "artiq.coredevice.dds"
                        and v["class"] in {"AD9858", "AD9914"}):
                    channel = v["arguments"]["channel"]
                    sysclk = v["arguments"]["sysclk"]
                    self.dds_widgets[channel] = _DDSWidget(
                        channel, sysclk, title)
                    self.dds_cb()
        except KeyError:
            pass

    def __delitem__(self, k):
        del self.ddb[k]
        if k in self.ttl_widgets:
            self.ttl_widgets[k].deleteLater()
            del self.ttl_widgets[k]
            self.ttl_cb()
        if k in self.dds_widgets:
            self.dds_widgets[k].deleteLater()
            del self.dds_widgets[k]
            self.dds_cb()

    def get_core_addr(self):
        try:
            comm = self.ddb["comm"]
            while isinstance(comm, str):
                comm = self.ddb[comm]
            return comm["arguments"]["host"]
        except KeyError:
            return None


class _MonInjDock(dockarea.Dock):
    def __init__(self, name):
        dockarea.Dock.__init__(self, name)

        self.grid = QtGui.QGridLayout()
        gridw = QtGui.QWidget()
        gridw.setLayout(self.grid)
        self.addWidget(gridw)

    def layout_widgets(self, widgets):
        w = self.grid.itemAt(0)
        while w is not None:
            self.grid.removeItem(w)
            w = self.grid.itemAt(0)
        for i, (_, w) in enumerate(sorted(widgets, key=itemgetter(0))):
            self.grid.addWidget(w, i // 4, i % 4)
            self.grid.setColumnStretch(i % 4, 1)


class MonInj(TaskObject):
    def __init__(self):
        self.ttl_dock = _MonInjDock("TTL")
        self.dds_dock = _MonInjDock("DDS")

        self.subscriber = Subscriber("devices", self.init_devices)
        self.dm = None
        self.transport = None

    async def start(self, server, port):
        loop = asyncio.get_event_loop()
        await loop.create_datagram_endpoint(lambda: self,
                                                 family=socket.AF_INET)
        try:
            await self.subscriber.connect(server, port)
            try:
                TaskObject.start(self)
            except:
                await self.subscriber.close()
                raise
        except:
            self.transport.close()
            raise

    async def stop(self):
        await TaskObject.stop(self)
        await self.subscriber.close()
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if self.dm is None:
            logger.debug("received datagram, but device manager "
                         "is not present yet")
            return
        try:
            ttl_levels, ttl_oes, ttl_overrides = \
                struct.unpack(">QQQ", data[:8*3])
            for w in self.dm.ttl_widgets.values():
                channel = w.channel
                w.set_value(ttl_levels & (1 << channel),
                            ttl_oes & (1 << channel),
                            ttl_overrides & (1 << channel))
            dds_data = data[8*3:]
            ndds = len(dds_data)//4
            ftws = struct.unpack(">" + "I"*ndds, dds_data)
            for w in self.dm.dds_widgets.values():
                try:
                    ftw = ftws[w.channel]
                except KeyError:
                    pass
                else:
                    w.set_value(ftw)
        except:
            logger.warning("failed to process datagram", exc_info=True)

    def error_received(self, exc):
        logger.warning("datagram endpoint error")

    def connection_lost(self, exc):
        self.transport = None

    def send_to_device(self, data):
        if self.dm is None:
            logger.debug("cannot sent to device yet, no device manager")
            return
        ca = self.dm.get_core_addr()
        logger.debug("core device address: %s", ca)
        if ca is None:
            logger.warning("could not find core device address")
        elif self.transport is None:
            logger.warning("datagram endpoint not available")
        else:
            self.transport.sendto(data, (ca, 3250))

    async def _do(self):
        while True:
            await asyncio.sleep(0.2)
            # MONINJ_REQ_MONITOR
            self.send_to_device(b"\x01")

    def init_devices(self, d):
        self.dm = _DeviceManager(self.send_to_device, d)
        self.dm.ttl_cb = lambda: self.ttl_dock.layout_widgets(
                            self.dm.ttl_widgets.items())
        self.dm.dds_cb = lambda: self.dds_dock.layout_widgets(
                            self.dm.dds_widgets.items())
        self.dm.ttl_cb()
        self.dm.dds_cb()
        return self.dm
