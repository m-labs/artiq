import asyncio
import logging
import textwrap
from collections import namedtuple

from PyQt5 import QtCore, QtWidgets, QtGui

from sipyco.sync_struct import Subscriber

from artiq.coredevice.comm_moninj import *
from artiq.coredevice.ad9910 import (
    _AD9910_REG_PROFILE0, _AD9910_REG_PROFILE7, 
    _AD9910_REG_FTW, _AD9910_REG_CFR1
)
from artiq.coredevice.ad9912_reg import AD9912_POW1, AD9912_SER_CONF
from artiq.gui.tools import LayoutWidget
from artiq.gui.flowlayout import FlowLayout


logger = logging.getLogger(__name__)

class _CancellableLineEdit(QtWidgets.QLineEdit):
    def escapePressedConnect(self, cb):
        self.esc_cb = cb

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            self.esc_cb(event)
        QtWidgets.QLineEdit.keyPressEvent(self, event)


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


class _DDSModel:
    def __init__(self, dds_type, ref_clk, cpld=None, pll=1, clk_div=0):
        self.cpld = cpld
        self.cur_frequency = 0
        self.cur_reg = 0
        self.dds_type = dds_type
        self.is_urukul = dds_type in ["AD9910", "AD9912"]
    
        if dds_type == "AD9914":
            self.ftw_per_hz = 2**32 / ref_clk
        else:
            if dds_type == "AD9910":
                max_freq = 1 << 32
                clk_mult = [4, 1, 2, 4]
            elif dds_type == "AD9912":  # AD9912
                max_freq = 1 << 48
                clk_mult = [1, 1, 2, 4]
            else:
                raise NotImplementedError
            sysclk = ref_clk / clk_mult[clk_div] * pll
            self.ftw_per_hz = 1 / sysclk * max_freq

    def monitor_update(self, probe, value):
        if self.dds_type == "AD9912":
            value = value << 16
        self.cur_frequency = self._ftw_to_freq(value)

    def _ftw_to_freq(self, ftw):
        return ftw / self.ftw_per_hz


class _DDSWidget(QtWidgets.QFrame):
    def __init__(self, dm, title, bus_channel=0, channel=0, dds_model=None):
        self.dm = dm
        self.bus_channel = bus_channel
        self.channel = channel
        self.dds_name = title
        self.cur_frequency = 0
        self.dds_model = dds_model

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

        # FREQ DATA/EDIT FIELD
        self.data_stack = QtWidgets.QStackedWidget()

        # page 1: display data
        grid_disp = LayoutWidget()
        grid_disp.layout.setContentsMargins(0, 0, 0, 0)
        grid_disp.layout.setHorizontalSpacing(0)
        grid_disp.layout.setVerticalSpacing(0)

        self.value_label = QtWidgets.QLabel()
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        grid_disp.addWidget(self.value_label, 0, 1, 1, 2)

        unit = QtWidgets.QLabel("MHz")
        unit.setAlignment(QtCore.Qt.AlignCenter)
        grid_disp.addWidget(unit, 0, 3, 1, 1)

        self.data_stack.addWidget(grid_disp)

        # page 2: edit data
        grid_edit = LayoutWidget()
        grid_edit.layout.setContentsMargins(0, 0, 0, 0)
        grid_edit.layout.setHorizontalSpacing(0)
        grid_edit.layout.setVerticalSpacing(0)

        self.value_edit = _CancellableLineEdit(self)
        self.value_edit.setAlignment(QtCore.Qt.AlignRight)
        grid_edit.addWidget(self.value_edit, 0, 1, 1, 2)
        unit = QtWidgets.QLabel("MHz")
        unit.setAlignment(QtCore.Qt.AlignCenter)
        grid_edit.addWidget(unit, 0, 3, 1, 1)
        self.data_stack.addWidget(grid_edit)

        grid.addWidget(self.data_stack, 2, 1)

        # BUTTONS
        self.button_stack = QtWidgets.QStackedWidget()

        # page 1: SET button
        set_grid = LayoutWidget()

        set_btn = QtWidgets.QToolButton()
        set_btn.setText("Set")
        set_btn.setToolTip("Set frequency")
        set_grid.addWidget(set_btn, 0, 1, 1, 1)
        
        # for urukuls also allow switching off RF
        if self.dds_model.is_urukul:
            off_btn = QtWidgets.QToolButton()
            off_btn.setText("Off")
            off_btn.setToolTip("Switch off the output")
            set_grid.addWidget(off_btn, 0, 2, 1, 1)

        self.button_stack.addWidget(set_grid)

        # page 2: apply/cancel buttons
        apply_grid = LayoutWidget()
        apply = QtWidgets.QToolButton()
        apply.setText("Apply")
        apply.setToolTip("Apply changes")
        apply_grid.addWidget(apply, 0, 1, 1, 1)
        cancel = QtWidgets.QToolButton()
        cancel.setText("Cancel")
        cancel.setToolTip("Cancel changes")
        apply_grid.addWidget(cancel, 0, 2, 1, 1)
        self.button_stack.addWidget(apply_grid)
        grid.addWidget(self.button_stack, 3, 1)

        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 1)
        grid.setRowStretch(3, 1)

        set_btn.clicked.connect(self.set_clicked)
        apply.clicked.connect(self.apply_changes)
        if self.dds_model.is_urukul:
            off_btn.clicked.connect(self.off_clicked)
            off_btn.setToolTip(textwrap.dedent(
                """Note: If TTL RTIO sw for the channel is switched high,
                this button will not disable the channel.
                Use the TTL override instead."""))
        self.value_edit.returnPressed.connect(lambda: self.apply_changes(None))
        self.value_edit.escapePressedConnect(self.cancel_changes)
        cancel.clicked.connect(self.cancel_changes)

        self.refresh_display()

    def set_clicked(self, set):
        self.data_stack.setCurrentIndex(1)
        self.button_stack.setCurrentIndex(1)
        self.value_edit.setText("{:.7f}"
                .format(self.cur_frequency/1e6))
        self.value_edit.setFocus()
        self.value_edit.selectAll()

    def off_clicked(self, set):
        self.dm.dds_channel_toggle(self.dds_name, self.dds_model, sw=False)
    
    def apply_changes(self, apply):
        self.data_stack.setCurrentIndex(0)
        self.button_stack.setCurrentIndex(0)
        frequency = float(self.value_edit.text())*1e6
        self.dm.dds_set_frequency(self.dds_name, self.dds_model, frequency)

    def cancel_changes(self, cancel):
        self.data_stack.setCurrentIndex(0)
        self.button_stack.setCurrentIndex(0)

    def refresh_display(self):
        self.cur_frequency = self.dds_model.cur_frequency
        self.value_label.setText("<font size=\"4\">{:.7f}</font>"
                           .format(self.cur_frequency/1e6))
        self.value_edit.setText("{:.7f}"
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
    mi_addr = None
    mi_port = None
    dds_sysclk = None
    description = set()

    for k, v in ddb.items():
        try:
            if isinstance(v, dict):
                comment = v.get("comment")
                if v["type"] == "local":
                    if v["module"] == "artiq.coredevice.ttl":
                        if "ttl_urukul" in k:
                            continue
                        channel = v["arguments"]["channel"]
                        force_out = v["class"] == "TTLOut"
                        widget = _WidgetDesc(k, comment, _TTLWidget, (channel, force_out, k))
                        description.add(widget)
                    elif (v["module"] == "artiq.coredevice.ad9914"
                            and v["class"] == "AD9914"):
                        bus_channel = v["arguments"]["bus_channel"]
                        channel = v["arguments"]["channel"]
                        dds_sysclk = v["arguments"]["sysclk"]
                        model = _DDSModel(v["class"], dds_sysclk)
                        widget = _WidgetDesc(k, comment, _DDSWidget, (k, bus_channel, channel, model))
                        description.add(widget)
                    elif (v["module"] == "artiq.coredevice.ad9910"
                                and v["class"] == "AD9910") or \
                            (v["module"] == "artiq.coredevice.ad9912"
                                and v["class"] == "AD9912"):
                        channel = v["arguments"]["chip_select"] - 4
                        if channel < 0:
                            continue
                        dds_cpld = v["arguments"]["cpld_device"]
                        spi_dev = ddb[dds_cpld]["arguments"]["spi_device"]
                        bus_channel = ddb[spi_dev]["arguments"]["channel"]
                        pll = v["arguments"]["pll_n"]
                        refclk = ddb[dds_cpld]["arguments"]["refclk"]
                        clk_div = v["arguments"].get("clk_div", 0)
                        model = _DDSModel( v["class"], refclk, dds_cpld, pll, clk_div)
                        widget = _WidgetDesc(k, comment, _DDSWidget, (k, bus_channel, channel, model))
                        description.add(widget)       
                    elif (   (v["module"] == "artiq.coredevice.ad53xx" and v["class"] == "AD53xx")
                          or (v["module"] == "artiq.coredevice.zotino" and v["class"] == "Zotino")):
                        spi_device = v["arguments"]["spi_device"]
                        spi_device = ddb[spi_device]
                        while isinstance(spi_device, str):
                            spi_device = ddb[spi_device]
                        spi_channel = spi_device["arguments"]["channel"]
                        for channel in range(32):
                            widget = _WidgetDesc((k, channel), comment, _DACWidget, (spi_channel, channel, k))
                            description.add(widget)
                elif v["type"] == "controller" and k == "core_moninj":
                    mi_addr = v["host"]
                    mi_port = v.get("port_proxy", 1383)
        except KeyError:
            pass
    return mi_addr, mi_port, description


class _DeviceManager:
    def __init__(self, schedule_ctl):
        self.mi_addr = None
        self.mi_port = None
        self.reconnect_mi = asyncio.Event()
        self.mi_connection = None
        self.mi_connector_task = asyncio.ensure_future(self.mi_connector())

        self.schedule_ctl = schedule_ctl

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
        mi_addr, mi_port, description = setup_from_ddb(self.ddb)

        if (mi_addr, mi_port) != (self.mi_addr, self.mi_port):
            self.mi_addr = mi_addr
            self.mi_port = mi_port
            self.reconnect_mi.set()

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
        if self.mi_connection is not None:
            widget = self.ttl_widgets[channel]
            if mode == "0":
                widget.cur_override = True
                widget.cur_level = False
                self.mi_connection.inject(channel, TTLOverride.level.value, 0)
                self.mi_connection.inject(channel, TTLOverride.oe.value, 1)
                self.mi_connection.inject(channel, TTLOverride.en.value, 1)
            elif mode == "1":
                widget.cur_override = True
                widget.cur_level = True
                self.mi_connection.inject(channel, TTLOverride.level.value, 1)
                self.mi_connection.inject(channel, TTLOverride.oe.value, 1)
                self.mi_connection.inject(channel, TTLOverride.en.value, 1)
            elif mode == "exp":
                widget.cur_override = False
                self.mi_connection.inject(channel, TTLOverride.en.value, 0)
            else:
                raise ValueError
            # override state may have changed
            widget.refresh_display()

    async def _submit_by_content(self, content, class_name, title):
        expid = {
            "log_level": logging.WARNING,
            "content": content,
            "class_name": class_name,
            "arguments": {}
        }
        scheduling = {
            "pipeline_name": "main",
            "priority": 0,
            "due_date": None,
            "flush": False
        }
        rid = await self.schedule_ctl.submit(
            scheduling["pipeline_name"],
            expid,
            scheduling["priority"], scheduling["due_date"],
            scheduling["flush"])
        logger.info("Submitted '%s', RID is %d", title, rid)

    def _dds_faux_injection(self, dds_channel, dds_model, action, title, log_msg):
        # create kernel and fill it in and send-by-content

        # initialize CPLD (if applicable)
        if dds_model.is_urukul:
            # urukuls need CPLD init and switch to on
            cpld_dev = """self.setattr_device("core_cache")
                self.setattr_device("{}")""".format(dds_model.cpld)

            # `sta`/`rf_sw`` variables are guaranteed for urukuls 
            # so {action} can use it
            # if there's no RF enabled, CPLD may have not been initialized
            # but if there is, it has been initialised - no need to do again
            cpld_init = """delay(15*ms)
                was_init = self.core_cache.get("_{cpld}_init")
                sta = self.{cpld}.sta_read()
                rf_sw = urukul_sta_rf_sw(sta)
                if rf_sw == 0 and len(was_init) == 0:
                    delay(15*ms)
                    self.{cpld}.init()
                    self.core_cache.put("_{cpld}_init", [1])
            """.format(cpld=dds_model.cpld)
        else:
            cpld_dev = ""
            cpld_init = ""

        # AD9912/9910: init channel (if uninitialized)
        if dds_model.dds_type == "AD9912":
            # 0xFF before init, 0x99 after
            channel_init = """
                if self.{dds_channel}.read({cfgreg}, length=1) == 0xFF:
                    delay(10*ms)
                    self.{dds_channel}.init()
            """.format(dds_channel=dds_channel, cfgreg=AD9912_SER_CONF)
        elif dds_model.dds_type == "AD9910":
            # -1 before init, 2 after
            channel_init = """
                if self.{dds_channel}.read32({cfgreg}) == -1:
                    delay(10*ms)
                    self.{dds_channel}.init()
            """.format(dds_channel=dds_channel, cfgreg=AD9912_SER_CONF)
        else:
            channel_init = "self.{dds_channel}.init()".format(dds_channel=dds_channel)

        dds_exp = textwrap.dedent("""
        from artiq.experiment import *
        from artiq.coredevice.urukul import *

        class {title}(EnvExperiment):
            def build(self):
                self.setattr_device("core")
                self.setattr_device("{dds_channel}")
                {cpld_dev}
                
            @kernel
            def run(self):
                self.core.break_realtime()
                {cpld_init}
                delay(10*ms)
                {channel_init}
                delay(15*ms)
                {action}
        """.format(title=title, action=action,
                   dds_channel=dds_channel,
                   cpld_dev=cpld_dev, cpld_init=cpld_init,
                   channel_init=channel_init))
        asyncio.ensure_future(
            self._submit_by_content(
                dds_exp, 
                title, 
                log_msg))

    def dds_set_frequency(self, dds_channel, dds_model, freq):
        action = "self.{ch}.set({freq})".format(
            freq=freq, ch=dds_channel)
        if dds_model.is_urukul:
            action += """
                ch_no = self.{ch}.chip_select - 4
                self.{cpld}.cfg_switches(rf_sw | 1 << ch_no)
            """.format(ch=dds_channel, cpld=dds_model.cpld)
        self._dds_faux_injection(
            dds_channel,
            dds_model,
            action,
            "SetDDS", 
            "Set DDS {} {}MHz".format(dds_channel, freq/1e6))

    def dds_channel_toggle(self, dds_channel, dds_model, sw=True):
        # urukul only
        if sw:
            switch = "| 1 << ch_no"
        else:
            switch = "& ~(1 << ch_no)"
        action = """
                ch_no = self.{dds_channel}.chip_select - 4
                self.{cpld}.cfg_switches(rf_sw {switch})
        """.format(
            dds_channel=dds_channel,
            cpld=dds_model.cpld,
            switch=switch
        )
        self._dds_faux_injection(
            dds_channel,
            dds_model,
            action,
            "ToggleDDS", 
            "Toggle DDS {} {}".format(dds_channel, "on" if sw else "off"))

    def setup_ttl_monitoring(self, enable, channel):
        if self.mi_connection is not None:
            self.mi_connection.monitor_probe(enable, channel, TTLProbe.level.value)
            self.mi_connection.monitor_probe(enable, channel, TTLProbe.oe.value)
            self.mi_connection.monitor_injection(enable, channel, TTLOverride.en.value)
            self.mi_connection.monitor_injection(enable, channel, TTLOverride.level.value)
            if enable:
                self.mi_connection.get_injection_status(channel, TTLOverride.en.value)

    def setup_dds_monitoring(self, enable, bus_channel, channel):
        if self.mi_connection is not None:
            self.mi_connection.monitor_probe(enable, bus_channel, channel)

    def setup_dac_monitoring(self, enable, spi_channel, channel):
        if self.mi_connection is not None:
            self.mi_connection.monitor_probe(enable, spi_channel, channel)

    def monitor_cb(self, channel, probe, value):
        if channel in self.ttl_widgets:
            widget = self.ttl_widgets[channel]
            if probe == TTLProbe.level.value:
                widget.cur_level = bool(value)
            elif probe == TTLProbe.oe.value:
                widget.cur_oe = bool(value)
            widget.refresh_display()
        elif (channel, probe) in self.dds_widgets:
            widget = self.dds_widgets[(channel, probe)]
            widget.dds_model.monitor_update(probe, value)
            widget.refresh_display()
        elif (channel, probe) in self.dac_widgets:
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
        logger.error("lost connection to moninj")
        self.reconnect_mi.set()

    async def mi_connector(self):
        while True:
            await self.reconnect_mi.wait()
            self.reconnect_mi.clear()
            if self.mi_connection is not None:
                await self.mi_connection.close()
                self.mi_connection = None
            new_mi_connection = CommMonInj(self.monitor_cb, self.injection_status_cb,
                    self.disconnect_cb)
            try:
                await new_mi_connection.connect(self.mi_addr, self.mi_port)
            except asyncio.CancelledError:
                logger.info("cancelled connection to moninj")
                break
            except:
                logger.error("failed to connect to moninj. Is aqctl_moninj_proxy running?", exc_info=True)
                await asyncio.sleep(10.)
                self.reconnect_mi.set()
            else:
                logger.info("ARTIQ dashboard connected to moninj (%s)",
                            self.mi_addr)
                self.mi_connection = new_mi_connection
                for ttl_channel in self.ttl_widgets.keys():
                    self.setup_ttl_monitoring(True, ttl_channel)
                for bus_channel, channel in self.dds_widgets.keys():
                    self.setup_dds_monitoring(True, bus_channel, channel)
                for spi_channel, channel in self.dac_widgets.keys():
                    self.setup_dac_monitoring(True, spi_channel, channel)

    async def close(self):
        self.mi_connector_task.cancel()
        try:
            await asyncio.wait_for(self.mi_connector_task, None)
        except asyncio.CancelledError:
            pass
        if self.mi_connection is not None:
            await self.mi_connection.close()


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
    def __init__(self, schedule_ctl):
        self.ttl_dock = _MonInjDock("TTL")
        self.dds_dock = _MonInjDock("DDS")
        self.dac_dock = _MonInjDock("DAC")

        self.dm = _DeviceManager(schedule_ctl)
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
