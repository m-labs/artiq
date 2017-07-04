import asyncio
import logging

from PyQt5 import QtCore, QtWidgets, QtGui

from artiq.protocols.sync_struct import Subscriber
from artiq.coredevice.comm_moninj import *
from artiq.gui.tools import LayoutWidget
from artiq.gui.flowlayout import FlowLayout


logger = logging.getLogger(__name__)


class _TTLWidget(QtWidgets.QFrame):
    def __init__(self, channel, set_mode, force_out, title):
        QtWidgets.QFrame.__init__(self)

        self.channel = channel
        self.set_mode = set_mode
        self.force_out = force_out

        self.setFrameShape(QtWidgets.QFrame.Box)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                            QtWidgets.QSizePolicy.Preferred)
        grid.addWidget(label, 1, 1)

        self.stack = QtWidgets.QStackedWidget()
        grid.addWidget(self.stack, 2, 1)

        self.direction = QtWidgets.QLabel()
        self.direction.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(self.direction)

        grid_cb = LayoutWidget()
        grid_cb.layout.setContentsMargins(0, 0, 0, 0)
        grid_cb.layout.setHorizontalSpacing(0)
        grid_cb.layout.setVerticalSpacing(0)
        self.override = QtWidgets.QToolButton()
        self.override.setText("OVR")
        self.override.setCheckable(True)
        self.override.setToolTip("Override")
        grid_cb.addWidget(self.override, 3, 1)
        self.level = QtWidgets.QToolButton()
        self.level.setText("LVL")
        self.level.setCheckable(True)
        self.level.setToolTip("Level")
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
        self.override.clicked.connect(self.override_toggled)
        self.level.clicked.connect(self.level_toggled)

        self.cur_level = False
        self.cur_oe = False
        self.cur_override = False
        self.refresh_display()

    def enterEvent(self, event):
        self.stack.setCurrentIndex(1)
        QtWidgets.QFrame.enterEvent(self, event)

    def leaveEvent(self, event):
        if not self.override.isChecked():
            self.stack.setCurrentIndex(0)
        QtWidgets.QFrame.leaveEvent(self, event)

    def override_toggled(self, override):
        if self.programmatic_change:
            return
        if override:
            if self.level.isChecked():
                self.set_mode(self.channel, "1")
            else:
                self.set_mode(self.channel, "0")
        else:
            self.set_mode(self.channel, "exp")

    def level_toggled(self, level):
        if self.programmatic_change:
            return
        if self.override.isChecked():
            if level:
                self.set_mode(self.channel, "1")
            else:
                self.set_mode(self.channel, "0")

    def refresh_display(self):
        value_s = "1" if self.cur_level else "0"
        if self.cur_override:
            value_s = "<b>" + value_s + "</b>"
            color = " color=\"red\""
        else:
            color = ""
        self.value.setText("<font size=\"5\"{}>{}</font>".format(
                            color, value_s))
        oe = self.cur_oe or self.force_out
        direction = "OUT" if oe else "IN"
        self.direction.setText("<font size=\"2\">" + direction + "</font>")

        self.programmatic_change = True
        try:
            self.override.setChecked(self.cur_override)
            if self.cur_override:
                self.stack.setCurrentIndex(1)
                self.level.setChecked(self.cur_level)
        finally:
            self.programmatic_change = False

    def sort_key(self):
        return self.channel


class _DDSWidget(QtWidgets.QFrame):
    def __init__(self, bus_channel, channel, title):
        QtWidgets.QFrame.__init__(self)

        self.bus_channel = bus_channel
        self.channel = channel

        self.setFrameShape(QtWidgets.QFrame.Box)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                    QtWidgets.QSizePolicy.Preferred)
        grid.addWidget(label, 1, 1)

        self.value = QtWidgets.QLabel()
        self.value.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self.value, 2, 1, 6, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 1)

        self.cur_frequency = 0
        self.refresh_display()

    def refresh_display(self):
        self.value.setText("<font size=\"4\">{:.7f}</font><font size=\"2\"> MHz</font>"
                           .format(self.cur_frequency/1e6))

    def sort_key(self):
        return (self.bus_channel, self.channel)


class _DeviceManager:
    def __init__(self, init):
        self.core_addr = None
        self.new_core_addr = asyncio.Event()
        self.core_connection = None
        self.core_connector_task = asyncio.ensure_future(self.core_connector())

        self.dds_sysclk = 0
        self.ttl_cb = lambda: None
        self.ttl_widgets = dict()
        self.ttl_widgets_by_channel = dict()
        self.dds_cb = lambda: None
        self.dds_widgets = dict()
        self.dds_widgets_by_channel = dict()
        for k, v in init.items():
            self[k] = v

    def __setitem__(self, k, v):
        if k in self.ttl_widgets:
            del self[k]
        if k in self.dds_widgets:
            del self[k]
        if not isinstance(v, dict):
            return
        try:
            if v["type"] == "local":
                widget = None
                if k == "core":
                    self.core_addr = v["arguments"]["host"]
                    self.new_core_addr.set()
                elif v["module"] == "artiq.coredevice.ttl":
                    channel = v["arguments"]["channel"]
                    force_out = v["class"] == "TTLOut"
                    widget = _TTLWidget(
                        channel, self.ttl_set_mode, force_out, k)
                    self.ttl_widgets[k] = widget
                    self.ttl_widgets_by_channel[channel] = widget
                    self.ttl_cb()
                    self.setup_ttl_monitoring(True, channel)
                elif (v["module"] == "artiq.coredevice.dds"
                        and v["class"] == "DDSGroupAD9914"):
                    self.dds_sysclk = v["arguments"]["sysclk"]
                elif (v["module"] == "artiq.coredevice.dds"
                        and v["class"] == "DDSChannelAD9914"):
                    bus_channel = v["arguments"]["bus_channel"]
                    channel = v["arguments"]["channel"]
                    widget = _DDSWidget(bus_channel, channel, k)
                    self.dds_widgets[k] = widget
                    self.dds_widgets_by_channel[(bus_channel, channel)] = widget
                    self.dds_cb()
                    self.setup_dds_monitoring(True, bus_channel, channel)
                if widget is not None and "comment" in v:
                    widget.setToolTip(v["comment"])
        except KeyError:
            pass

    def __delitem__(self, k):
        if k in self.ttl_widgets:
            widget = self.ttl_widgets[k]
            self.setup_ttl_monitoring(False, widget.channel)
            widget.deleteLater()
            del self.ttl_widgets_by_channel[widget.channel]
            del self.ttl_widgets[k]
            self.ttl_cb()
        if k in self.dds_widgets:
            widget = self.dds_widgets[k]
            self.setup_dds_monitoring(False, widget.bus_channel, widget.channel)
            widget.deleteLater()
            del self.dds_widgets_by_channel[(widget.bus_channel, widget.channel)]
            del self.dds_widgets[k]
            self.dds_cb()

    def ttl_set_mode(self, channel, mode):
        if self.core_connection is not None:
            widget = self.ttl_widgets_by_channel[channel]
            if mode == "0":
                widget.cur_override = True
                widget.cur_level = False
                self.core_connection.inject(channel, TTLOverride.level.value, 0)
                self.core_connection.inject(channel, TTLOverride.oe.value, 1)
                self.core_connection.inject(channel, TTLOverride.en.value, 1)
            elif mode == "1":
                widget.cur_override = True
                widget.cur_level = True
                self.core_connection.inject(channel, TTLOverride.level.value, 1)
                self.core_connection.inject(channel, TTLOverride.oe.value, 1)
                self.core_connection.inject(channel, TTLOverride.en.value, 1)
            elif mode == "exp":
                widget.cur_override = False
                self.core_connection.inject(channel, TTLOverride.en.value, 0)
            else:
                raise ValueError
            # override state may have changed
            widget.refresh_display()

    def setup_ttl_monitoring(self, enable, channel):
        if self.core_connection is not None:
            self.core_connection.monitor(enable, channel, TTLProbe.level.value)
            self.core_connection.monitor(enable, channel, TTLProbe.oe.value)
            if enable:
                self.core_connection.get_injection_status(channel, TTLOverride.en.value)

    def setup_dds_monitoring(self, enable, bus_channel, channel):
        if self.core_connection is not None:
            self.core_connection.monitor(enable, bus_channel, channel)

    def monitor_cb(self, channel, probe, value):
        if channel in self.ttl_widgets_by_channel:
            widget = self.ttl_widgets_by_channel[channel]
            if probe == TTLProbe.level.value:
                widget.cur_level = bool(value)
            elif probe == TTLProbe.oe.value:
                widget.cur_oe = bool(value)
            widget.refresh_display()
        if (channel, probe) in self.dds_widgets_by_channel:
            widget = self.dds_widgets_by_channel[(channel, probe)]
            widget.cur_frequency = value*self.dds_sysclk/2**32
            widget.refresh_display()

    def injection_status_cb(self, channel, override, value):
        if channel in self.ttl_widgets_by_channel:
            self.ttl_widgets_by_channel[channel].cur_override = bool(value)

    async def core_connector(self):
        while True:
            await self.new_core_addr.wait()
            self.new_core_addr.clear()
            if self.core_connection is not None:
                await self.core_connection.close()
                self.core_connection = None
            new_core_connection = CommMonInj(self.monitor_cb, self.injection_status_cb,
                    lambda: logger.error("lost connection to core device moninj"))
            try:
                await new_core_connection.connect(self.core_addr, 1383)
            except:
                logger.error("failed to connect to core device moninj", exc_info=True)
            else:
                self.core_connection = new_core_connection
                for ttl_channel in self.ttl_widgets_by_channel.keys():
                    self.setup_ttl_monitoring(True, ttl_channel)
                for bus_channel, channel in self.dds_widgets_by_channel.keys():
                    self.setup_dds_monitoring(True, bus_channel, channel)

    async def close(self):
        self.core_connector_task.cancel()
        try:
            await asyncio.wait_for(self.core_connector_task, None)
        except asyncio.CancelledError:
            pass
        if self.core_connection is not None:
            await self.core_connection.close()


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

        for _, w in sorted(widgets, key=lambda i: i[1].sort_key()):
            grid.addWidget(w)

        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(grid_widget)


class MonInj:
    def __init__(self):
        self.ttl_dock = _MonInjDock("TTL")
        self.dds_dock = _MonInjDock("DDS")

        self.subscriber = Subscriber("devices", self.init_devices)
        self.dm = None

    async def start(self, server, port):
        await self.subscriber.connect(server, port)

    async def stop(self):
        await self.subscriber.close()
        if self.dm is not None:
            await self.dm.close()

    def init_devices(self, d):
        self.dm = _DeviceManager(d)
        self.dm.ttl_cb = lambda: self.ttl_dock.layout_widgets(
                            self.dm.ttl_widgets.items())
        self.dm.dds_cb = lambda: self.dds_dock.layout_widgets(
                            self.dm.dds_widgets.items())
        self.dm.ttl_cb()
        self.dm.dds_cb()
        return self.dm
