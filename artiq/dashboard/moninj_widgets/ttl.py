import asyncio

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QToolButton, QStackedWidget, QLabel, QSizePolicy, QGridLayout, QFrame

from artiq.coredevice.comm_moninj import TTLOverride, TTLProbe
from artiq.dashboard.moninj_widgets import MoninjWidget
from artiq.gui.tools import LayoutWidget


class TTLWidget(MoninjWidget):
    def __init__(self, dm, channel, force_out, title):
        QFrame.__init__(self)

        self.channel = channel
        self.dm = dm
        self.force_out = force_out

        self.setFrameShape(QFrame.Box)
        self.setFrameShadow(QFrame.Raised)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        self.setLayout(grid)
        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        label.setSizePolicy(QSizePolicy.Ignored,
                            QSizePolicy.Preferred)
        grid.addWidget(label, 1, 1)

        self.stack = QStackedWidget()
        grid.addWidget(self.stack, 2, 1)

        self.direction = QLabel()
        self.direction.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.direction)

        grid_cb = LayoutWidget()
        grid_cb.layout.setContentsMargins(0, 0, 0, 0)
        grid_cb.layout.setHorizontalSpacing(0)
        grid_cb.layout.setVerticalSpacing(0)
        self.override = QToolButton()
        self.override.setText("OVR")
        self.override.setCheckable(True)
        self.override.setToolTip("Override")
        grid_cb.addWidget(self.override, 3, 1)
        self.level = QToolButton()
        self.level.setText("LVL")
        self.level.setCheckable(True)
        self.level.setToolTip("Level")
        grid_cb.addWidget(self.level, 3, 2)
        self.stack.addWidget(grid_cb)

        self.value = QLabel()
        self.value.setAlignment(Qt.AlignCenter)
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
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.override.isChecked():
            self.stack.setCurrentIndex(0)
        super().leaveEvent(event)

    def override_toggled(self, override):
        if self.programmatic_change:
            return
        self.set_mode(("1" if self.level.isChecked() else "0") if override else "exp")

    def level_toggled(self, level):
        if self.programmatic_change:
            return
        self.set_mode("1" if level else "0")

    def refresh_display(self):
        level = self.cur_override_level if self.cur_override else self.cur_level
        value_s = "1" if level else "0"

        if self.cur_override:
            value_s = f"<b>{value_s}</b>"
            color = ' color="red"'
        else:
            color = ""
        self.value.setText(f'<font size="5"{color}>{value_s}</font>')
        self.direction.setText(f'<font size="2">{"OUT" if self.force_out or self.cur_oe else "IN"}</font>')

        try:
            self.programmatic_change = True
            self.override.setChecked(self.cur_override)
            if self.cur_override:
                self.stack.setCurrentIndex(1)
                self.level.setChecked(level)
        finally:
            self.programmatic_change = False

    @property
    def sort_key(self):
        return self.channel

    def setup_monitoring(self, enable):
        if conn := self.dm.comm:
            conn.monitor_probe(enable, self.channel, TTLProbe.level.value)
            conn.monitor_probe(enable, self.channel, TTLProbe.oe.value)
            conn.monitor_injection(enable, self.channel, TTLOverride.en.value)
            conn.monitor_injection(enable, self.channel, TTLOverride.level.value)
            if enable:
                conn.get_injection_status(self.channel, TTLOverride.en.value)

    def set_mode(self, mode):
        if conn := self.dm.comm:
            if mode == "0":
                self.cur_override = True
                self.cur_level = False
                conn.inject(self.channel, TTLOverride.level.value, 0)
                conn.inject(self.channel, TTLOverride.oe.value, 1)
                conn.inject(self.channel, TTLOverride.en.value, 1)
            elif mode == "1":
                self.cur_override = True
                self.cur_level = True
                conn.inject(self.channel, TTLOverride.level.value, 1)
                conn.inject(self.channel, TTLOverride.oe.value, 1)
                conn.inject(self.channel, TTLOverride.en.value, 1)
            elif mode == "exp":
                self.cur_override = False
                conn.inject(self.channel, TTLOverride.en.value, 0)
            else:
                raise ValueError
            # override state may have changed
            self.refresh_display()

    def on_monitor(self, probe, value):
        if probe == TTLProbe.level.value:
            self.cur_level = bool(value)
        elif probe == TTLProbe.oe.value:
            self.cur_oe = bool(value)
        self.refresh_display()

    def on_injection_status(self, override, value):
        if override == TTLOverride.en.value:
            self.cur_override = bool(value)
        if override == TTLOverride.level.value:
            self.cur_override_level = bool(value)
        self.refresh_display()
