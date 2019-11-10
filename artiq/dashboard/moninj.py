import asyncio
import logging
from collections import namedtuple

from PyQt5 import QtCore, QtWidgets, QtGui

from sipyco.sync_struct import Subscriber

from artiq.coredevice.comm_moninj import *
from artiq.gui.tools import LayoutWidget
from artiq.gui.flowlayout import FlowLayout


logger = logging.getLogger(__name__)


class _TTLWidget(QtWidgets.QFrame):
    def __init__(self, dm, channel, force_out, title):
        QtWidgets.QFrame.__init__(self)

        self.channel = channel
        self.set_mode = dm.ttl_set_mode
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
        self.cur_override_level = False
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
        level = self.cur_override_level if self.cur_override else self.cur_level
        value_s = "1" if level else "0"

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


class _SimpleDisplayWidget(QtWidgets.QFrame):
    def __init__(self, title):
        QtWidgets.QFrame.__init__(self)

        self.setFrameShape(QtWidgets.QFrame.Box)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(label, 1, 1)

        self.value = QtWidgets.QLabel()
        self.value.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self.value, 2, 1, 6, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 1)

        self.refresh_display()

    def refresh_display(self):
        raise NotImplementedError

    def sort_key(self):
        raise NotImplementedError


class _DDSWidget(_SimpleDisplayWidget):
    def __init__(self, dm, bus_channel, channel, title):
        self.bus_channel = bus_channel
        self.channel = channel
        self.cur_frequency = 0
        _SimpleDisplayWidget.__init__(self, title)

    def refresh_display(self):
        self.value.setText("<font size=\"4\">{:.7f}</font><font size=\"2\"> MHz</font>"
                           .format(self.cur_frequency/1e6))

    def sort_key(self):
        return (self.bus_channel, self.channel)


class _DACWidget(_SimpleDisplayWidget):
    def __init__(self, dm, spi_channel, channel, title):
        self.spi_channel = spi_channel
        self.channel = channel
        self.cur_value = 0
        _SimpleDisplayWidget.__init__(self, "{} ch{}".format(title, channel))

    def refresh_display(self):
        self.value.setText("<font size=\"4\">{:.3f}</font><font size=\"2\"> %</font>"
                           .format(self.cur_value*100/2**16))

    def sort_key(self):
        return (self.spi_channel, self.channel)


_WidgetDesc = namedtuple("_WidgetDesc", "uid comment cls arguments")


def setup_from_ddb(ddb):
    core_addr = None
    dds_sysclk = None
    description = set()

    for k, v in ddb.items():
        comment = None
        if "comment" in v:
            comment = v["comment"]
        try:
            if isinstance(v, dict) and v["type"] == "local":
                if k == "core":
                    core_addr = v["arguments"]["host"]
                elif v["module"] == "artiq.coredevice.ttl":
                    channel = v["arguments"]["channel"]
                    force_out = v["class"] == "TTLOut"
                    widget = _WidgetDesc(k, comment, _TTLWidget, (channel, force_out, k))
                    description.add(widget)
                elif (v["module"] == "artiq.coredevice.ad9914"
                        and v["class"] == "AD9914"):
                    bus_channel = v["arguments"]["bus_channel"]
                    channel = v["arguments"]["channel"]
                    dds_sysclk = v["arguments"]["sysclk"]
                    widget = _WidgetDesc(k, comment, _DDSWidget, (bus_channel, channel, k))
                    description.add(widget)
                elif (   (v["module"] == "artiq.coredevice.ad53xx" and v["class"] == "AD53XX")
                      or (v["module"] == "artiq.coredevice.zotino" and v["class"] == "Zotino")):
                    spi_device = v["arguments"]["spi_device"]
                    spi_device = ddb[spi_device]
                    while isinstance(spi_device, str):
                        spi_device = ddb[spi_device]
                    spi_channel = spi_device["arguments"]["channel"]
                    for channel in range(32):
                        widget = _WidgetDesc((k, channel), comment, _DACWidget, (spi_channel, channel, k))
                        description.add(widget)
        except KeyError:
            pass
    return core_addr, dds_sysclk, description


class _DeviceManager:
    def __init__(self):
        self.core_addr = None
        self.reconnect_core = asyncio.Event()
        self.core_connection = None
        self.core_connector_task = asyncio.ensure_future(self.core_connector())

        self.ddb = dict()
        self.description = set()
        self.widgets_by_uid = dict()

        self.dds_sysclk = 0
        self.ttl_cb = lambda: None
        self.ttl_widgets = dict()
        self.dds_cb = lambda: None
        self.dds_widgets = dict()
        self.dac_cb = lambda: None
        self.dac_widgets = dict()

    def init_ddb(self, ddb):
        self.ddb = ddb
        return ddb

    def notify(self, mod):
        core_addr, dds_sysclk, description = setup_from_ddb(self.ddb)

        if core_addr != self.core_addr:
            self.core_addr = core_addr
            self.reconnect_core.set()

        self.dds_sysclk = dds_sysclk

        for to_remove in self.description - description:
            widget = self.widgets_by_uid[to_remove.uid]
            del self.widgets_by_uid[to_remove.uid]

            if isinstance(widget, _TTLWidget):
                self.setup_ttl_monitoring(False, widget.channel)
                widget.deleteLater()
                del self.ttl_widgets[widget.channel]
                self.ttl_cb()
            elif isinstance(widget, _DDSWidget):
                self.setup_dds_monitoring(False, widget.bus_channel, widget.channel)
                widget.deleteLater()
                del self.dds_widgets[(widget.bus_channel, widget.channel)]
                self.dds_cb()
            elif isinstance(widget, _DACWidget):
                self.setup_dac_monitoring(False, widget.spi_channel, widget.channel)
                widget.deleteLater()
                del self.dac_widgets[(widget.spi_channel, widget.channel)]
                self.dac_cb()     
            else:
                raise ValueError

        for to_add in description - self.description:
            widget = to_add.cls(self, *to_add.arguments)
            if to_add.comment is not None:
                widget.setToolTip(to_add.comment)
            self.widgets_by_uid[to_add.uid] = widget

            if isinstance(widget, _TTLWidget):
                self.ttl_widgets[widget.channel] = widget
                self.ttl_cb()
                self.setup_ttl_monitoring(True, widget.channel)
            elif isinstance(widget, _DDSWidget):
                self.dds_widgets[(widget.bus_channel, widget.channel)] = widget
                self.dds_cb()
                self.setup_dds_monitoring(True, widget.bus_channel, widget.channel)
            elif isinstance(widget, _DACWidget):
                self.dac_widgets[(widget.spi_channel, widget.channel)] = widget
                self.dac_cb()
                self.setup_dac_monitoring(True, widget.spi_channel, widget.channel)
            else:
                raise ValueError

        self.description = description

    def ttl_set_mode(self, channel, mode):
        if self.core_connection is not None:
            widget = self.ttl_widgets[channel]
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
            self.core_connection.monitor_probe(enable, channel, TTLProbe.level.value)
            self.core_connection.monitor_probe(enable, channel, TTLProbe.oe.value)
            self.core_connection.monitor_injection(enable, channel, TTLOverride.en.value)
            self.core_connection.monitor_injection(enable, channel, TTLOverride.level.value)
            if enable:
                self.core_connection.get_injection_status(channel, TTLOverride.en.value)

    def setup_dds_monitoring(self, enable, bus_channel, channel):
        if self.core_connection is not None:
            self.core_connection.monitor_probe(enable, bus_channel, channel)

    def setup_dac_monitoring(self, enable, spi_channel, channel):
        if self.core_connection is not None:
            self.core_connection.monitor_probe(enable, spi_channel, channel)

    def monitor_cb(self, channel, probe, value):
        if channel in self.ttl_widgets:
            widget = self.ttl_widgets[channel]
            if probe == TTLProbe.level.value:
                widget.cur_level = bool(value)
            elif probe == TTLProbe.oe.value:
                widget.cur_oe = bool(value)
            widget.refresh_display()
        if (channel, probe) in self.dds_widgets:
            widget = self.dds_widgets[(channel, probe)]
            widget.cur_frequency = value*self.dds_sysclk/2**32
            widget.refresh_display()
        if (channel, probe) in self.dac_widgets:
            widget = self.dac_widgets[(channel, probe)]
            widget.cur_value = value
            widget.refresh_display()

    def injection_status_cb(self, channel, override, value):
        if channel in self.ttl_widgets:
            widget = self.ttl_widgets[channel]
            if override == TTLOverride.en.value:
                widget.cur_override = bool(value)
            if override == TTLOverride.level.value:
                widget.cur_override_level = bool(value)
            widget.refresh_display()

    def disconnect_cb(self):
        logger.error("lost connection to core device moninj")
        self.reconnect_core.set()

    async def core_connector(self):
        while True:
            await self.reconnect_core.wait()
            self.reconnect_core.clear()
            if self.core_connection is not None:
                await self.core_connection.close()
                self.core_connection = None
            new_core_connection = CommMonInj(self.monitor_cb, self.injection_status_cb,
                    self.disconnect_cb)
            try:
                await new_core_connection.connect(self.core_addr, 1383)
            except:
                logger.error("failed to connect to core device moninj", exc_info=True)
                await asyncio.sleep(10.)
                self.reconnect_core.set()
            else:
                self.core_connection = new_core_connection
                for ttl_channel in self.ttl_widgets.keys():
                    self.setup_ttl_monitoring(True, ttl_channel)
                for bus_channel, channel in self.dds_widgets.keys():
                    self.setup_dds_monitoring(True, bus_channel, channel)
                for spi_channel, channel in self.dac_widgets.keys():
                    self.setup_dac_monitoring(True, spi_channel, channel)

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

        for widget in sorted(widgets, key=lambda w: w.sort_key()):
            grid.addWidget(widget)

        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(grid_widget)


class MonInj:
    def __init__(self):
        self.ttl_dock = _MonInjDock("TTL")
        self.dds_dock = _MonInjDock("DDS")
        self.dac_dock = _MonInjDock("DAC")

        self.dm = _DeviceManager()
        self.dm.ttl_cb = lambda: self.ttl_dock.layout_widgets(
                            self.dm.ttl_widgets.values())
        self.dm.dds_cb = lambda: self.dds_dock.layout_widgets(
                            self.dm.dds_widgets.values())
        self.dm.dac_cb = lambda: self.dac_dock.layout_widgets(
                            self.dm.dac_widgets.values())

        self.subscriber = Subscriber("devices", self.dm.init_ddb, self.dm.notify)

    async def start(self, server, port):
        await self.subscriber.connect(server, port)

    async def stop(self):
        await self.subscriber.close()
        if self.dm is not None:
            await self.dm.close()
