import asyncio
import logging
from collections import namedtuple

from PyQt5 import QtCore, QtWidgets, QtGui
from numpy import int64

from sipyco.sync_struct import Subscriber

from artiq.coredevice.ad9910 import *
from artiq.coredevice.ad9912_reg import *
from artiq.coredevice.comm_moninj import *
from artiq.gui.tools import LayoutWidget
from artiq.gui.flowlayout import FlowLayout
from artiq.language.units import MHz

logger = logging.getLogger(__name__)


class _TTLWidget(QtWidgets.QFrame):
    def __init__(self, dm, channel, force_out, title):
        super().__init__()

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

        self.override.toggled.connect(self.override_toggled)
        self.override.toggled.connect(self.refresh_display)

        self.level.toggled.connect(self.level_toggled)
        self.level.toggled.connect(self.refresh_display)

        self.cur_oe = False
        self.cur_override_level = False

    @property
    def cur_level(self):
        return self.cur_override_level if self.override.isChecked() else self.level.isChecked()

    def enterEvent(self, event):
        self.stack.setCurrentIndex(1)
        QtWidgets.QFrame.enterEvent(self, event)

    def leaveEvent(self, event):
        if not self.override.isChecked():
            self.stack.setCurrentIndex(0)
        QtWidgets.QFrame.leaveEvent(self, event)

    def override_toggled(self, override):
        self.set_mode(self.channel, ("1" if self.level.isChecked() else "0") if override else "exp")

    def level_toggled(self, level):
        self.set_mode(self.channel, "1" if level else "0")

    def refresh_display(self):
        value_s = "1" if self.cur_level else "0"

        if self.override.isChecked():
            value_s = f"<b>{value_s}</b>"
            color = ' color="red"'
        else:
            color = ""
        self.value.setText(f'<font size="5"{color}>{value_s}</font>')
        self.direction.setText(f'<font size="2">{"OUT" if self.force_out or self.cur_oe else "IN"}</font>')

        if self.override.isChecked():
            self.stack.setCurrentIndex(1)

    @property
    def sort_key(self):
        return self.channel

    def on_monitor(self, probe, value):
        if probe == TTLProbe.level.value:
            self.level.setChecked(bool(value))
        elif probe == TTLProbe.oe.value:
            self.cur_oe = bool(value)

    def on_injection_status(self, override, value):
        if override == TTLOverride.en.value:
            self.override.setChecked(bool(value))
        if override == TTLOverride.level.value:
            self.cur_override_level = bool(value)

class _SimpleDisplayWidget(QtWidgets.QFrame):
    def __init__(self, title):
        super().__init__()

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

    def refresh_display(self):
        raise NotImplementedError

    @property
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

    @property
    def sort_key(self):
        return self.bus_channel, self.channel


class _DACWidget(_SimpleDisplayWidget):
    def __init__(self, dm, spi_channel, channel, title):
        self.spi_channel = spi_channel
        self.channel = channel
        self.cur_value = 0
        super().__init__("{} ch{}".format(title, channel))

    def refresh_display(self):
        self.value.setText("<font size=\"4\">{:.3f}</font><font size=\"2\"> %</font>"
                           .format(self.cur_value*100/2**16))

    @property
    def sort_key(self):
        return self.spi_channel, self.channel


class _UrukulWidget(QtWidgets.QFrame):
    def __init__(self, dm, bus_channel, channel, title, sw_channel, ref_clk, pll, is_9910, clk_div=0):
        super().__init__()
        self.bus_channel = bus_channel
        self.channel = channel
        self.dm = dm
        self.title = title
        self.sw_channel = sw_channel
        self.ref_clk = ref_clk
        self.pll = pll
        self.is_9910 = is_9910
        self.clk_div = clk_div

        self.setFrameShape(QtWidgets.QFrame.Box)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(0)
        self.setLayout(grid)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setMinimumWidth(100)
        label.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                            QtWidgets.QSizePolicy.Preferred)
        grid.addWidget(label, 1, 1)

        self.stack = QtWidgets.QStackedWidget()
        grid.addWidget(self.stack, 2, 1)

        self.on_off_label = QtWidgets.QLabel()
        self.on_off_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(self.on_off_label)

        grid_cb = LayoutWidget()
        grid_cb.layout.setContentsMargins(0, 0, 0, 0)
        grid_cb.layout.setSpacing(0)
        self.override = QtWidgets.QToolButton()
        self.override.setText("OVR")
        self.override.setCheckable(True)
        self.override.setToolTip("Override")
        grid_cb.addWidget(self.override, 1, 1)
        self.level = QtWidgets.QToolButton()
        self.level.setText("LVL")
        self.level.setCheckable(True)
        self.level.setToolTip("Level")
        grid_cb.addWidget(self.level, 1, 2)
        self.stack.addWidget(grid_cb)

        grid_freq = QtWidgets.QGridLayout()
        grid_freq.setContentsMargins(0, 0, 0, 0)
        grid_freq.setSpacing(0)
        self.freq_stack = QtWidgets.QStackedWidget()
        grid_freq.addWidget(self.freq_stack, 1, 1)
        self.freq_label = QtWidgets.QLabel()
        self.freq_label.setAlignment(QtCore.Qt.AlignCenter)
        self.freq_label.setMaximumWidth(100)
        self.freq_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                      QtWidgets.QSizePolicy.Preferred)
        self.freq_stack.addWidget(self.freq_label)
        unit = QtWidgets.QLabel()
        unit.setAlignment(QtCore.Qt.AlignCenter)
        unit.setText(' MHz')
        grid_freq.addWidget(unit, 1, 2)
        grid_freq.setColumnStretch(1, 1)
        grid_freq.setColumnStretch(2, 0)
        grid.addLayout(grid_freq, 3, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 0)
        grid.setRowStretch(4, 1)

        self.override.toggled.connect(self.override_toggled)
        self.override.toggled.connect(self.refresh_display)
        self.level.toggled.connect(self.refresh_display)

        self.cur_frequency_low = 0
        self.cur_frequency_high = 0
        self.cur_amp = 0
        self.cur_reg = 0

        max_freq, clk_mult = (1 << 32, [4, 1, 2, 4]) if is_9910 else (1 << 48, [1, 1, 2, 4])
        sysclk = ref_clk / clk_mult[clk_div] * pll
        self.ftw_per_hz = 1 / sysclk * max_freq

        # TTL Widget of Urukul
        self.ttl = None

    def on_all_widgets_initialized(self):
        docks = self.dm.ttl_widgets
        if docks:
            ttl = docks[self.sw_channel]
            if ttl:
                self.ttl = ttl
                self.override.toggled.connect(ttl.override.setChecked)
                self.level.toggled.connect(ttl.level.setChecked)
                ttl.override.toggled.connect(self.override.setChecked)
                ttl.level.toggled.connect(self.level.setChecked)

    @property
    def cur_freq(self):
        return (self.cur_frequency_low + self.cur_frequency_high) / MHz

    def enterEvent(self, event):
        self.stack.setCurrentIndex(1)
        self.freq_stack.setCurrentIndex(1)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.stack.setCurrentIndex(0)
        self.freq_stack.setCurrentIndex(0)
        super().leaveEvent(event)

    def override_toggled(self, override):
        comm = self.dm.core_connection
        if comm:
            comm.inject(self.bus_channel, 0, int(override))

    def update_reg(self, reg):
        if self.is_9910:
            self.cur_reg = (reg >> 24) & 0xff
        else:
            self.cur_reg = ((reg >> 16) & ~(3 << 13)) & 0xffff

    def update_data_high(self, data):
        if self.is_9910:
            if AD9910_REG_PROFILE0() <= self.cur_reg <= AD9910_REG_PROFILE7():
                asf = (data >> 16) & 0xffff
                self.cur_amp = self._asf_to_amp(asf)
        else:
            if self.cur_reg == AD9912_POW1:
                ftw = self._ftw_to_freq(int64(data & 0xffff) << 32)
                self.cur_frequency_high = ftw

    def update_data_low(self, data):
        if self.is_9910:
            if (AD9910_REG_PROFILE0() <= self.cur_reg <= AD9910_REG_PROFILE7() or
                    self.cur_reg == AD9910_REG_FTW()):
                self.cur_frequency_low = self._ftw_to_freq(data)
            elif self.cur_reg == AD9910_REG_ASF():
                self.cur_amp = self._asf_to_amp(data)
        else:
            if self.cur_reg == AD9912_POW1:
                # mask to avoid improper sign extension
                ftw = self._ftw_to_freq(int64(data & 0xffffffff))
                self.cur_frequency_low = ftw

    def _ftw_to_freq(self, ftw):
        return ftw / self.ftw_per_hz

    @staticmethod
    def _asf_to_amp(asf):
        return asf / float(0x3ffe)  # coredevice.ad9912 doesn't allow amplitude control so only need to worry about 9910

    def refresh_display(self):
        on_off_s = "ON" if self.ttl.cur_level else "OFF"

        if self.override.isChecked():
            on_off_s = f"<b>{on_off_s}</b>"
            color = ' color="red"'
        else:
            color = ""
        self.on_off_label.setText(f'<font size="2">{on_off_s}</font>')
        self.freq_label.setText(f'<font size="4"{color}>{self.cur_freq:.3f}</font>')
        if self.override.isChecked():
            self.stack.setCurrentIndex(1)

    @property
    def sort_key(self):
        return self.bus_channel, self.channel

    def setup_monitoring(self, enable):
        comm = self.dm.core_connection
        if comm:
            comm.monitor_probe(enable, self.bus_channel, self.channel)  # register addresses
            comm.monitor_probe(enable, self.bus_channel, self.channel + 4)  # first data
            comm.monitor_probe(enable, self.bus_channel, self.channel + 8)  # second data
            if self.channel == 0:
                comm.monitor_injection(enable, self.bus_channel, 0)
                comm.monitor_injection(enable, self.bus_channel, 1)
                comm.monitor_injection(enable, self.bus_channel, 2)
                if enable:
                    comm.get_injection_status(self.bus_channel, 0)

    def on_monitor(self, probe, value):
        type = probe // 4
        if type == 0:  # probes 0-3: register addresses
            self.update_reg(value)
        elif type == 1:  # probes 4-7: data_high (for 64 bit transfer)
            self.update_data_high(value)
        elif type == 2:  # probes 8-11: data_low (for 64 bit) or just data (32 bit)
            self.update_data_low(value)

    @staticmethod
    def extract_key(*, channel, probe, **_):
        return channel, probe % 4


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
            if not isinstance(v, dict):
                continue
            if v["type"] == "local":
                args, module_, class_ = v["arguments"], v["module"], v["class"]
                if k == "core":
                    core_addr = args["host"]
                is_ad9910 = module_ == "artiq.coredevice.ad9910" and class_ == "AD9910"
                is_ad9912 = module_ == "artiq.coredevice.ad9912" and class_ == "AD9912"
                is_ad9914 = module_ == "artiq.coredevice.ad9914" and class_ == "AD9914"
                is_ad53xx = module_ == "artiq.coredevice.ad53xx" and class_ == "AD53XX"
                is_zotino = module_ == "artiq.coredevice.zotino" and class_ == "Zotino"
                if module_ == "artiq.coredevice.ttl":
                    channel = args["channel"]
                    description.add(_WidgetDesc(k, comment, _TTLWidget, (
                        channel, class_ == "TTLOut", k)))
                elif is_ad9914:
                    dds_sysclk, bus_channel, channel = args["sysclk"], args[
                        "bus_channel"], args["channel"]
                    description.add(_WidgetDesc(k, comment, _DDSWidget,
                                                (bus_channel, channel, k)))
                elif is_ad53xx or is_zotino:
                    spi_device = ddb[args["spi_device"]]
                    while isinstance(spi_device, str):
                        spi_device = ddb[spi_device]
                    spi_channel = spi_device["arguments"]["channel"]
                    for channel in range(32):
                        widget = _WidgetDesc((k, channel), comment, _DACWidget, (spi_channel, channel, k))
                        description.add(widget)
                elif is_ad9910 or is_ad9912:
                    urukul_device = ddb[args["cpld_device"]]
                    sw_channel = ddb[args["sw_device"]]["arguments"]["channel"]
                    channel = args["chip_select"] - 4
                    pll = args["pll_n"]
                    refclk = urukul_device["arguments"]["refclk"]
                    spi_device = ddb[urukul_device["arguments"]["spi_device"]]
                    spi_channel = spi_device["arguments"]["channel"]
                    widget = _WidgetDesc(k, comment, _UrukulWidget,
                                         (spi_channel, channel, k, sw_channel, refclk, pll, is_ad9910))
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
        self.urukul_cb = lambda: None
        self.urukul_widgets = dict()

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
            elif isinstance(widget, _UrukulWidget):
                widget.setup_monitoring(False)
                widget.deleteLater()
                del self.urukul_widgets[widget.sort_key]
                self.urukul_cb()
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
            elif isinstance(widget, _UrukulWidget):
                self.urukul_widgets[widget.sort_key] = widget
                self.urukul_cb()
                widget.setup_monitoring(True)
            else:
                raise ValueError

        self.description = description

    def ttl_set_mode(self, channel, mode):
        if self.core_connection is not None:
            widget = self.ttl_widgets[channel]
            if mode == "0":
                widget.override.setChecked(True)
                widget.level.setChecked(False)
                self.core_connection.inject(channel, TTLOverride.level.value, 0)
                self.core_connection.inject(channel, TTLOverride.oe.value, 1)
                self.core_connection.inject(channel, TTLOverride.en.value, 1)
            elif mode == "1":
                widget.override.setChecked(True)
                widget.level.setChecked(True)
                self.core_connection.inject(channel, TTLOverride.level.value, 1)
                self.core_connection.inject(channel, TTLOverride.oe.value, 1)
                self.core_connection.inject(channel, TTLOverride.en.value, 1)
            elif mode == "exp":
                widget.override.setChecked(False)
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
            widget.on_monitor(probe, value)
            widget.refresh_display()
        if (channel, probe) in self.dds_widgets:
            widget = self.dds_widgets[(channel, probe)]
            widget.cur_frequency = value*self.dds_sysclk/2**32
            widget.refresh_display()
        if (channel, probe) in self.dac_widgets:
            widget = self.dac_widgets[(channel, probe)]
            widget.cur_value = value
            widget.refresh_display()
        if (channel, probe % 4) in self.urukul_widgets:
            widget = self.urukul_widgets[(channel, probe % 4)]
            widget.on_monitor(probe, value)
            widget.refresh_display()

    def injection_status_cb(self, channel, override, value):
        if channel in self.ttl_widgets:
            widget = self.ttl_widgets[channel]
            widget.on_injection_status(override, value)
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
            except asyncio.CancelledError:
                logger.info("cancelled connection to core device moninj")
                break
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
                for widget in self.urukul_widgets.values():
                    widget.setup_monitoring(True)

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

        for widget in sorted(widgets, key=lambda w: w.sort_key):
            grid.addWidget(widget)

        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(grid_widget)


class MonInj:
    def __init__(self):
        self.ttl_dock = _MonInjDock("TTL")
        self.dds_dock = _MonInjDock("DDS")
        self.dac_dock = _MonInjDock("DAC")
        self.urukul_dock = _MonInjDock("Urukul")

        self.dm = _DeviceManager()
        self.dm.ttl_cb = lambda: self.ttl_dock.layout_widgets(
                            self.dm.ttl_widgets.values())
        self.dm.dds_cb = lambda: self.dds_dock.layout_widgets(
                            self.dm.dds_widgets.values())
        self.dm.dac_cb = lambda: self.dac_dock.layout_widgets(
                            self.dm.dac_widgets.values())
        self.dm.urukul_cb = lambda: self.urukul_dock.layout_widgets(
                            self.dm.urukul_widgets.values())


        self.subscriber = Subscriber("devices", self.dm.init_ddb, self.dm.notify)

    async def start(self, server, port):
        await self.subscriber.connect(server, port)

    async def stop(self):
        await self.subscriber.close()
        if self.dm is not None:
            await self.dm.close()
