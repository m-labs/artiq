import asyncio
import logging
import socket
import struct
from operator import itemgetter

from PyQt5 import QtCore, QtWidgets

from artiq.tools import TaskObject
from artiq.protocols.sync_struct import Subscriber


logger = logging.getLogger(__name__)


_mode_enc = {
    "exp": 0,
    "1": 1,
    "0": 2,
    "in": 3
}


class _TTLWidget(QtWidgets.QFrame):
    def __init__(self, channel, send_to_device, force_out, title):
        self.channel = channel
        self.send_to_device = send_to_device
        self.force_out = force_out

        QtWidgets.QFrame.__init__(self)

        self.setFrameShape(QtWidgets.QFrame.Box)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        grid = QtWidgets.QGridLayout()
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        grid.addWidget(label, 1, 1)

        self._direction = QtWidgets.QLabel()
        self._direction.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self._direction, 2, 1)
        self._override = QtWidgets.QLabel()
        self._override.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self._override, 3, 1)
        self._value = QtWidgets.QLabel()
        self._value.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self._value, 4, 1, 6, 1)

        self._value.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        menu = QtWidgets.QActionGroup(self._value)
        menu.setExclusive(True)
        self._expctl_action = QtWidgets.QAction("Experiment controlled", self._value)
        self._expctl_action.setCheckable(True)
        menu.addAction(self._expctl_action)
        self._value.addAction(self._expctl_action)
        self._expctl_action.triggered.connect(lambda: self.set_mode("exp"))
        separator = QtWidgets.QAction(self._value)
        separator.setSeparator(True)
        self._value.addAction(separator)
        self._force1_action = QtWidgets.QAction("Force 1", self._value)
        self._force1_action.setCheckable(True)
        menu.addAction(self._force1_action)
        self._value.addAction(self._force1_action)
        self._force1_action.triggered.connect(lambda: self.set_mode("1"))
        self._force0_action = QtWidgets.QAction("Force 0", self._value)
        self._force0_action.setCheckable(True)
        menu.addAction(self._force0_action)
        self._value.addAction(self._force0_action)
        self._force0_action.triggered.connect(lambda: self.set_mode("0"))
        self._forcein_action = QtWidgets.QAction("Force input", self._value)
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


class _DDSWidget(QtWidgets.QFrame):
    def __init__(self, bus_channel, channel, sysclk, title):
        self.bus_channel = bus_channel
        self.channel = channel
        self.sysclk = sysclk

        QtWidgets.QFrame.__init__(self)

        self.setFrameShape(QtWidgets.QFrame.Panel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        grid = QtWidgets.QGridLayout()
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        grid.addWidget(label, 1, 1)

        self._value = QtWidgets.QLabel()
        self._value.setAlignment(QtCore.Qt.AlignCenter)
        self._value.setWordWrap(True)
        grid.addWidget(self._value, 2, 1, 6, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 1)

        self.set_value(0)

    def set_value(self, ftw):
        frequency = ftw*self.sysclk()/2**32
        self._value.setText("<font size=\"6\">{:.7f} MHz</font>"
                            .format(float(frequency)/1e6))


class _DeviceManager:
    def __init__(self, send_to_device, init):
        self.dds_sysclk = 0
        self.send_to_device = send_to_device
        self.ddb = dict()
        self.ttl_cb = lambda: None
        self.ttl_widgets = dict()
        self.dds_cb = lambda: None
        self.dds_widgets = dict()
        for k, v in init.items():
            self[k] = v

    def get_dds_sysclk(self):
        return self.dds_sysclk

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
                        and v["class"] == "CoreDDS"):
                    self.dds_sysclk = v["arguments"]["sysclk"]
                if (v["module"] == "artiq.coredevice.dds"
                        and v["class"] in {"AD9858", "AD9914"}):
                    bus_channel = v["arguments"]["bus_channel"]
                    channel = v["arguments"]["channel"]
                    self.dds_widgets[channel] = _DDSWidget(
                        bus_channel, channel, self.get_dds_sysclk, title)
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


class _MonInjDock(QtWidgets.QDockWidget):
    def __init__(self, name):
        QtWidgets.QDockWidget.__init__(self, name)
        self.setObjectName(name)
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)


    def layout_widgets(self, widgets):
        scroll_area = QtWidgets.QScrollArea()
        self.setWidget(scroll_area)

        grid = QtWidgets.QGridLayout()
        grid_widget = QtWidgets.QWidget()
        grid_widget.setLayout(grid)

        for i, (_, w) in enumerate(sorted(widgets, key=itemgetter(0))):
            grid.addWidget(w, i // 4, i % 4)
            grid.setColumnStretch(i % 4, 1)

        scroll_area.setWidget(grid_widget)


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
            hlen = 8*3+4
            (ttl_levels, ttl_oes, ttl_overrides,
             dds_rtio_first_channel, dds_channels_per_bus) = \
                struct.unpack(">QQQHH", data[:hlen])
            for w in self.dm.ttl_widgets.values():
                channel = w.channel
                w.set_value(ttl_levels & (1 << channel),
                            ttl_oes & (1 << channel),
                            ttl_overrides & (1 << channel))
            dds_data = data[hlen:]
            ndds = len(dds_data)//4
            ftws = struct.unpack(">" + "I"*ndds, dds_data)
            for w in self.dm.dds_widgets.values():
                offset = (dds_channels_per_bus*w.bus_channel
                          + w.channel-dds_rtio_first_channel)
                try:
                    ftw = ftws[offset]
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
