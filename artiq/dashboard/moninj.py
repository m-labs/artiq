import asyncio
import logging
import socket
import struct
from operator import itemgetter

from PyQt5 import QtCore, QtWidgets, QtGui

from artiq.tools import TaskObject
from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import LayoutWidget
from artiq.gui.flowlayout import FlowLayout


logger = logging.getLogger(__name__)


_mode_enc = {
    "exp": 0,
    "1": 1,
    "0": 2,
    "in": 3
}


class _MoninjWidget(QtWidgets.QFrame):
    def __init__(self):
        QtWidgets.QFrame.__init__(self)
        qfm = QtGui.QFontMetrics(self.font())
        self._size = QtCore.QSize(
            18*qfm.averageCharWidth(),
            6*qfm.lineSpacing())
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        self.setFrameShape(QtWidgets.QFrame.Box)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

    def sizeHint(self):
        return self._size


class _TTLWidget(_MoninjWidget):
    def __init__(self, channel, send_to_device, force_out, title):
        self.channel = channel
        self.send_to_device = send_to_device
        self.force_out = force_out

        _MoninjWidget.__init__(self)

        grid = QtWidgets.QGridLayout()
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        grid.addWidget(label, 1, 1)

        self.stack = QtWidgets.QStackedWidget()
        grid.addWidget(self.stack, 2, 1)

        self.direction = QtWidgets.QLabel()
        self.direction.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(self.direction)

        grid_cb = LayoutWidget()
        self.override = QtWidgets.QCheckBox("Override")
        grid_cb.addWidget(self.override, 3, 1)
        self.level = QtWidgets.QCheckBox("Level")
        grid_cb.addWidget(self.level, 3, 2)
        self.stack.addWidget(grid_cb)

        self.value = QtWidgets.QLabel()
        self.value.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self.value, 3, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 0)
        grid.setRowStretch(4, 1)

        self.programmatic_change = False
        self.override.stateChanged.connect(self.override_toggled)
        self.level.stateChanged.connect(self.level_toggled)

        self.set_value(0, False, False)

    def enterEvent(self, event):
        self.stack.setCurrentIndex(1)
        _MoninjWidget.enterEvent(self, event)

    def leaveEvent(self, event):
        if not self.override.isChecked():
            self.stack.setCurrentIndex(0)
        _MoninjWidget.leaveEvent(self, event)

    def override_toggled(self, override):
        if self.programmatic_change:
            return
        if override:
            if self.level.isChecked():
                self.set_mode("1")
            else:
                self.set_mode("0")
        else:
            self.set_mode("exp")

    def level_toggled(self, level):
        if self.programmatic_change:
            return
        if self.override.isChecked():
            if level:
                self.set_mode("1")
            else:
                self.set_mode("0")

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
        else:
            color = ""
        self.value.setText("<font size=\"9\"{}>{}</font>".format(
                            color, value_s))
        oe = oe or self.force_out
        direction = "OUT" if oe else "IN"
        self.direction.setText("<font size=\"1\">" + direction + "</font>")

        self.programmatic_change = True
        try:
            self.override.setChecked(bool(override))
            if override:
                self.stack.setCurrentIndex(1)
                self.level.setChecked(bool(value))
        finally:
            self.programmatic_change = False


class _DDSWidget(_MoninjWidget):
    def __init__(self, bus_channel, channel, sysclk, title):
        self.bus_channel = bus_channel
        self.channel = channel
        self.sysclk = sysclk

        _MoninjWidget.__init__(self)

        grid = QtWidgets.QGridLayout()
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        grid.addWidget(label, 1, 1)

        self.value = QtWidgets.QLabel()
        self.value.setAlignment(QtCore.Qt.AlignCenter)
        self.value.setWordWrap(True)
        grid.addWidget(self.value, 2, 1, 6, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 1)

        self.set_value(0)

    def set_value(self, ftw):
        frequency = ftw*self.sysclk()/2**32
        self.value.setText("<font size=\"5\">{:.7f} MHz</font>"
                           .format(frequency/1e6))


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
                widget = None
                if v["module"] == "artiq.coredevice.ttl":
                    channel = v["arguments"]["channel"]
                    force_out = v["class"] == "TTLOut"
                    widget = _TTLWidget(
                        channel, self.send_to_device, force_out, k)
                    self.ttl_widgets[k] = widget
                    self.ttl_cb()
                if (v["module"] == "artiq.coredevice.dds"
                        and v["class"] == "CoreDDS"):
                    self.dds_sysclk = v["arguments"]["sysclk"]
                if (v["module"] == "artiq.coredevice.dds"
                        and v["class"] in {"AD9858", "AD9914"}):
                    bus_channel = v["arguments"]["bus_channel"]
                    channel = v["arguments"]["channel"]
                    widget = _DDSWidget(
                        bus_channel, channel, self.get_dds_sysclk, k)
                    self.dds_widgets[channel] = widget
                    self.dds_cb()
                if widget is not None and "comment" in v:
                    widget.setToolTip(v["comment"])
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

        grid = FlowLayout()
        grid_widget = QtWidgets.QWidget()
        grid_widget.setLayout(grid)

        for _, w in sorted(widgets, key=itemgetter(0)):
            grid.addWidget(w)

        scroll_area.setWidgetResizable(True)
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
                bus_nr = w.bus_channel - dds_rtio_first_channel
                offset = dds_channels_per_bus*bus_nr + w.channel
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
