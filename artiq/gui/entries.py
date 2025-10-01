import logging
from collections import OrderedDict
from functools import partial

from PyQt6 import QtCore, QtGui, QtWidgets

from artiq.gui.tools import LayoutWidget, disable_scroll_wheel, WheelFilter
from artiq.gui.scanwidget import ScanWidget
from artiq.gui.scientific_spinbox import ScientificSpinBox


logger = logging.getLogger(__name__)


class EntryTreeWidget(QtWidgets.QTreeWidget):
    quickStyleClicked = QtCore.pyqtSignal()

    def __init__(self):
        QtWidgets.QTreeWidget.__init__(self)
        self.setColumnCount(3)
        self.header().setStretchLastSection(False)
        if hasattr(self.header(), "setSectionResizeMode"):
            set_resize_mode = self.header().setSectionResizeMode
        else:
            set_resize_mode = self.header().setResizeMode
        set_resize_mode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        set_resize_mode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        set_resize_mode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.header().setVisible(False)
        self.setSelectionMode(self.SelectionMode.NoSelection)
        self.setHorizontalScrollMode(self.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(self.ScrollMode.ScrollPerPixel)

        self.viewport().installEventFilter(WheelFilter(self.viewport(), True))

        self._groups = dict()
        self._arg_to_widgets = dict()
        self._arguments = dict()

        self.set_background_color()
        self.gradient = QtGui.QLinearGradient(
            0, 0, 0, QtGui.QFontMetrics(self.font()).lineSpacing() * 2.5)
        self.set_gradient_color()
        self.set_group_color()

        self.bottom_item = QtWidgets.QTreeWidgetItem()
        self.addTopLevelItem(self.bottom_item)

    def set_background_color(self, color=None):
        if color is None:
            base_color = self.palette().base().color()
        else:
            base_color = QtGui.QColor(color)
        self.palette().setColor(QtGui.QPalette.ColorRole.Base, base_color)

    def set_gradient_color(self, color=None):
        if color is None:
            start_color = self.palette().base().color()
            end_color = self.palette().midlight().color()
        else:
            start_color = QtGui.QColor(color)
            end_color = start_color.toHsv()
            end_color.setHsv(end_color.hue(),
                             int(end_color.saturation() * 0.8),
                             min(255, int(end_color.value() * 1.2)))
        self.gradient.setColorAt(0, start_color)
        self.gradient.setColorAt(1, end_color)
        for widgets in self._arg_to_widgets.values():
            for col in range(3):
                widgets["widget_item"].setBackground(col, self.gradient)

    def set_group_color(self, color=None):
        if color is None:
            group_color = self.palette().mid().color()
        else:
            group_color = QtGui.QColor(color)
        for group in self._groups.values():
            for col in range(3):
                group.setBackground(col, group_color)

    def set_argument(self, key, argument):
        self._arguments[key] = argument
        widgets = dict()
        self._arg_to_widgets[key] = widgets
        entry_class = procdesc_to_entry(argument["desc"])
        if "state" not in argument:
            argument["state"] = entry_class.default_state(argument["desc"])
        entry = entry_class(argument)
        if argument["desc"].get("quickstyle"):
            entry.quickStyleClicked.connect(self.quickStyleClicked)
        widget_item = QtWidgets.QTreeWidgetItem([key])
        if argument["tooltip"]:
            widget_item.setToolTip(0, argument["tooltip"])
        widgets["entry"] = entry
        widgets["widget_item"] = widget_item

        self.set_gradient_color()
        font = widget_item.font(0)
        font.setBold(True)
        widget_item.setFont(0, font)

        if argument["group"] is None:
            self.insertTopLevelItem(self.indexFromItem(self.bottom_item).row(), widget_item)
        else:
            self._get_group(argument["group"]).addChild(widget_item)
        fix_layout = LayoutWidget()
        widgets["fix_layout"] = fix_layout
        fix_layout.addWidget(entry)
        self.setItemWidget(widget_item, 1, fix_layout)

        reset_entry = QtWidgets.QToolButton()
        reset_entry.setToolTip("Reset to default value")
        reset_entry.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_BrowserReload))
        reset_entry.clicked.connect(partial(self.reset_entry, key))

        disable_other_scans = QtWidgets.QToolButton()
        widgets["disable_other_scans"] = disable_other_scans
        disable_other_scans.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton))
        disable_other_scans.setToolTip("Disable other scans")
        disable_other_scans.clicked.connect(
            partial(self._disable_other_scans, key))
        if not isinstance(entry, ScanEntry):
            disable_other_scans.setVisible(False)

        tool_buttons = LayoutWidget()
        tool_buttons.layout.setRowStretch(0, 1)
        tool_buttons.layout.setRowStretch(3, 1)
        tool_buttons.addWidget(reset_entry, 1)
        tool_buttons.addWidget(disable_other_scans, 2)
        self.setItemWidget(widget_item, 2, tool_buttons)

    def _get_group(self, key):
        if key in self._groups:
            return self._groups[key]
        group = QtWidgets.QTreeWidgetItem([key])
        for col in range(3):
            font = group.font(col)
            font.setBold(True)
            group.setFont(col, font)
        self.insertTopLevelItem(self.indexFromItem(self.bottom_item).row(), group)
        self._groups[key] = group
        self.set_group_color()
        return group

    def _disable_other_scans(self, current_key):
        for key, widgets in self._arg_to_widgets.items():
            if (key != current_key and isinstance(widgets["entry"], ScanEntry)):
                widgets["entry"].disable()

    def update_argument(self, key, argument):
        widgets = self._arg_to_widgets[key]

        # Qt needs a setItemWidget() to handle layout correctly,
        # simply replacing the entry inside the LayoutWidget
        # results in a bug.

        widgets["entry"].deleteLater()
        widgets["entry"] = procdesc_to_entry(argument["desc"])(argument)
        widgets["disable_other_scans"].setVisible(
            isinstance(widgets["entry"], ScanEntry))
        widgets["fix_layout"].deleteLater()
        widgets["fix_layout"] = LayoutWidget()
        widgets["fix_layout"].addWidget(widgets["entry"])
        self.setItemWidget(widgets["widget_item"], 1, widgets["fix_layout"])
        self.updateGeometries()

    def reset_entry(self, key):
        procdesc = self._arguments[key]["desc"]
        self._arguments[key]["state"] = procdesc_to_entry(procdesc).default_state(procdesc)
        self.update_argument(key, self._arguments[key])

    def save_state(self):
        expanded = []
        for k, v in self._groups.items():
            if v.isExpanded():
                expanded.append(k)
        return {
            "expanded": expanded,
            "scroll": self.verticalScrollBar().value()
        }

    def restore_state(self, state):
        for e in state["expanded"]:
            try:
                self._groups[e].setExpanded(True)
            except KeyError:
                pass
        self.verticalScrollBar().setValue(state["scroll"])


class StringEntry(QtWidgets.QLineEdit):
    def __init__(self, argument):
        QtWidgets.QLineEdit.__init__(self)
        self.setText(argument["state"])
        def update(text):
            argument["state"] = text
        self.textEdited.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        return procdesc.get("default", "")


class BooleanEntry(QtWidgets.QCheckBox):
    def __init__(self, argument):
        QtWidgets.QCheckBox.__init__(self)
        self.setChecked(argument["state"])
        def update(checked):
            argument["state"] = bool(checked)
        self.stateChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        return procdesc.get("default", False)


class EnumerationEntry(QtWidgets.QWidget):
    quickStyleClicked = QtCore.pyqtSignal()

    def __init__(self, argument):
        QtWidgets.QWidget.__init__(self)
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        procdesc = argument["desc"]
        choices = procdesc["choices"]
        if procdesc["quickstyle"]:
            self.btn_group = QtWidgets.QButtonGroup()
            for i, choice in enumerate(choices):
                button = QtWidgets.QPushButton(choice)
                self.btn_group.addButton(button)
                self.btn_group.setId(button, i)
                layout.addWidget(button)

            def submit(index):
                argument["state"] = choices[index]
                self.quickStyleClicked.emit()
            self.btn_group.idClicked.connect(submit)
        else:
            self.combo_box = QtWidgets.QComboBox()
            disable_scroll_wheel(self.combo_box)
            self.combo_box.addItems(choices)
            idx = choices.index(argument["state"])
            self.combo_box.setCurrentIndex(idx)
            layout.addWidget(self.combo_box)

            def update(index):
                argument["state"] = choices[index]
            self.combo_box.currentIndexChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        if "default" in procdesc:
            return procdesc["default"]
        else:
            return procdesc["choices"][0]


class NumberEntryInt(QtWidgets.QSpinBox):
    def __init__(self, argument):
        QtWidgets.QSpinBox.__init__(self)
        disable_scroll_wheel(self)
        procdesc = argument["desc"]
        self.setSingleStep(procdesc["step"])
        if procdesc["min"] is not None:
            self.setMinimum(procdesc["min"])
        else:
            self.setMinimum(-((1 << 31) - 1))
        if procdesc["max"] is not None:
            self.setMaximum(procdesc["max"])
        else:
            self.setMaximum((1 << 31) - 1)
        if procdesc["unit"]:
            self.setSuffix(" " + procdesc["unit"])

        self.setValue(argument["state"])
        def update(value):
            argument["state"] = value
        self.valueChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        if "default" in procdesc:
            return procdesc["default"]
        else:
            have_max = "max" in procdesc and procdesc["max"] is not None
            have_min = "min" in procdesc and procdesc["min"] is not None
            if have_max and have_min:
                if procdesc["min"] <= 0 < procdesc["max"]:
                    return 0
            elif have_min and not have_max:
                if procdesc["min"] >= 0:
                    return procdesc["min"]
            elif not have_min and have_max:
                if procdesc["max"] < 0:
                    return procdesc["max"]
            return 0


class NumberEntryFloat(ScientificSpinBox):
    def __init__(self, argument):
        ScientificSpinBox.__init__(self)
        disable_scroll_wheel(self)
        procdesc = argument["desc"]
        scale = procdesc["scale"]
        self.setDecimals(procdesc["precision"])
        self.setSigFigs()
        self.setSingleStep(procdesc["step"]/scale)
        self.setRelativeStep()
        if procdesc["min"] is not None:
            self.setMinimum(procdesc["min"]/scale)
        else:
            self.setMinimum(float("-inf"))
        if procdesc["max"] is not None:
            self.setMaximum(procdesc["max"]/scale)
        else:
            self.setMaximum(float("inf"))
        if procdesc["unit"]:
            self.setSuffix(" " + procdesc["unit"])

        self.setValue(argument["state"]/scale)
        def update(value):
            argument["state"] = value*scale
        self.valueChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        if "default" in procdesc:
            return procdesc["default"]
        else:
            return 0.0


class _NoScan(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        scale = procdesc["scale"]
        self.value = ScientificSpinBox()
        disable_scroll_wheel(self.value)
        self.value.setDecimals(procdesc["precision"])
        self.value.setSigFigs()
        if procdesc["global_min"] is not None:
            self.value.setMinimum(procdesc["global_min"]/scale)
        else:
            self.value.setMinimum(float("-inf"))
        if procdesc["global_max"] is not None:
            self.value.setMaximum(procdesc["global_max"]/scale)
        else:
            self.value.setMaximum(float("inf"))
        self.value.setSingleStep(procdesc["global_step"]/scale)
        self.value.setRelativeStep()
        if procdesc["unit"]:
            self.value.setSuffix(" " + procdesc["unit"])
        self.addWidget(QtWidgets.QLabel("Value:"), 0, 0)
        self.addWidget(self.value, 0, 1)

        self.value.setValue(state["value"]/scale)
        def update(value):
            state["value"] = value*scale
        self.value.valueChanged.connect(update)

        self.repetitions = QtWidgets.QSpinBox()
        self.repetitions.setMinimum(1)
        self.repetitions.setMaximum((1 << 31) - 1)
        disable_scroll_wheel(self.repetitions)
        self.addWidget(QtWidgets.QLabel("Repetitions:"), 1, 0)
        self.addWidget(self.repetitions, 1, 1)

        self.repetitions.setValue(state["repetitions"])

        def update_repetitions(value):
            state["repetitions"] = value
        self.repetitions.valueChanged.connect(update_repetitions)


class _RangeScan(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        scale = procdesc["scale"]

        def apply_properties(widget):
            widget.setDecimals(procdesc["precision"])
            if procdesc["global_min"] is not None:
                widget.setMinimum(procdesc["global_min"]/scale)
            else:
                widget.setMinimum(float("-inf"))
            if procdesc["global_max"] is not None:
                widget.setMaximum(procdesc["global_max"]/scale)
            else:
                widget.setMaximum(float("inf"))
            if procdesc["global_step"] is not None:
                widget.setSingleStep(procdesc["global_step"]/scale)
            if procdesc["unit"]:
                widget.setSuffix(" " + procdesc["unit"])

        scanner = ScanWidget()
        disable_scroll_wheel(scanner)
        self.addWidget(scanner, 0, 0, -1, 1)

        start = ScientificSpinBox()
        start.setStyleSheet("QDoubleSpinBox {color:blue}")
        disable_scroll_wheel(start)
        self.addWidget(start, 0, 1)

        npoints = QtWidgets.QSpinBox()
        npoints.setMinimum(1)
        npoints.setMaximum((1 << 31) - 1)
        disable_scroll_wheel(npoints)
        self.addWidget(npoints, 1, 1)

        stop = ScientificSpinBox()
        stop.setStyleSheet("QDoubleSpinBox {color:red}")
        disable_scroll_wheel(stop)
        self.addWidget(stop, 2, 1)

        randomize = QtWidgets.QCheckBox("Randomize")
        self.addWidget(randomize, 3, 1)

        self.layout.setColumnStretch(0, 4)
        self.layout.setColumnStretch(1, 1)

        apply_properties(start)
        start.setSigFigs()
        start.setRelativeStep()
        apply_properties(stop)
        stop.setSigFigs()
        stop.setRelativeStep()
        apply_properties(scanner)

        def update_start(value):
            state["start"] = value*scale
            scanner.setStart(value)
            if start.value() != value:
                start.setValue(value)

        def update_stop(value):
            state["stop"] = value*scale
            scanner.setStop(value)
            if stop.value() != value:
                stop.setValue(value)

        def update_npoints(value):
            state["npoints"] = value
            scanner.setNum(value)
            if npoints.value() != value:
                npoints.setValue(value)

        def update_randomize(value):
            state["randomize"] = value
            randomize.setChecked(value)

        scanner.startChanged.connect(update_start)
        scanner.numChanged.connect(update_npoints)
        scanner.stopChanged.connect(update_stop)
        start.valueChanged.connect(update_start)
        npoints.valueChanged.connect(update_npoints)
        stop.valueChanged.connect(update_stop)
        randomize.stateChanged.connect(update_randomize)
        scanner.setStart(state["start"]/scale)
        scanner.setNum(state["npoints"])
        scanner.setStop(state["stop"]/scale)
        randomize.setChecked(state["randomize"])


class _CenterScan(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        scale = procdesc["scale"]

        def apply_properties(widget):
            widget.setDecimals(procdesc["precision"])
            if procdesc["global_min"] is not None:
                widget.setMinimum(procdesc["global_min"]/scale)
            else:
                widget.setMinimum(float("-inf"))
            if procdesc["global_max"] is not None:
                widget.setMaximum(procdesc["global_max"]/scale)
            else:
                widget.setMaximum(float("inf"))
            if procdesc["global_step"] is not None:
                widget.setSingleStep(procdesc["global_step"]/scale)
            if procdesc["unit"]:
                widget.setSuffix(" " + procdesc["unit"])

        center = ScientificSpinBox()
        disable_scroll_wheel(center)
        apply_properties(center)
        center.setSigFigs()
        center.setRelativeStep()
        center.setValue(state["center"]/scale)
        self.addWidget(center, 0, 1)
        self.addWidget(QtWidgets.QLabel("Center:"), 0, 0)

        span = ScientificSpinBox()
        disable_scroll_wheel(span)
        apply_properties(span)
        span.setSigFigs()
        span.setRelativeStep()
        span.setMinimum(0)
        span.setValue(state["span"]/scale)
        self.addWidget(span, 1, 1)
        self.addWidget(QtWidgets.QLabel("Span:"), 1, 0)

        step = ScientificSpinBox()
        disable_scroll_wheel(step)
        apply_properties(step)
        step.setSigFigs()
        step.setRelativeStep()
        step.setMinimum(0)
        step.setValue(state["step"]/scale)
        self.addWidget(step, 2, 1)
        self.addWidget(QtWidgets.QLabel("Step:"), 2, 0)

        randomize = QtWidgets.QCheckBox("Randomize")
        self.addWidget(randomize, 3, 1)
        randomize.setChecked(state["randomize"])

        def update_center(value):
            state["center"] = value*scale

        def update_span(value):
            state["span"] = value*scale

        def update_step(value):
            state["step"] = value*scale

        def update_randomize(value):
            state["randomize"] = value

        center.valueChanged.connect(update_center)
        span.valueChanged.connect(update_span)
        step.valueChanged.connect(update_step)
        randomize.stateChanged.connect(update_randomize)


class _ExplicitScan(LayoutWidget):
    def __init__(self, state):
        LayoutWidget.__init__(self)

        self.value = QtWidgets.QLineEdit()
        self.addWidget(QtWidgets.QLabel("Sequence:"), 0, 0)
        self.addWidget(self.value, 0, 1)

        float_regexp = r"(([+-]?\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)"
        regexp = "(float)?( +float)* *".replace("float", float_regexp)
        self.value.setValidator(QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(regexp)))

        self.value.setText(" ".join([str(x) for x in state["sequence"]]))
        def update(text):
            if self.value.hasAcceptableInput():
                state["sequence"] = [float(x) for x in text.split()]
        self.value.textEdited.connect(update)


class ScanEntry(LayoutWidget):
    def __init__(self, argument):
        LayoutWidget.__init__(self)
        self.argument = argument

        self.stack = QtWidgets.QStackedWidget()
        self.addWidget(self.stack, 1, 0, colspan=4)

        procdesc = argument["desc"]
        state = argument["state"]
        self.widgets = OrderedDict()
        self.widgets["NoScan"] = _NoScan(procdesc, state["NoScan"])
        self.widgets["RangeScan"] = _RangeScan(procdesc, state["RangeScan"])
        self.widgets["CenterScan"] = _CenterScan(procdesc, state["CenterScan"])
        self.widgets["ExplicitScan"] = _ExplicitScan(state["ExplicitScan"])
        for widget in self.widgets.values():
            self.stack.addWidget(widget)

        self.radiobuttons = OrderedDict()
        self.radiobuttons["NoScan"] = QtWidgets.QRadioButton("No scan")
        self.radiobuttons["RangeScan"] = QtWidgets.QRadioButton("Range")
        self.radiobuttons["CenterScan"] = QtWidgets.QRadioButton("Center")
        self.radiobuttons["ExplicitScan"] = QtWidgets.QRadioButton("Explicit")
        scan_type = QtWidgets.QButtonGroup()
        for n, b in enumerate(self.radiobuttons.values()):
            self.addWidget(b, 0, n)
            scan_type.addButton(b)
            b.toggled.connect(self._scan_type_toggled)

        selected = argument["state"]["selected"]
        self.radiobuttons[selected].setChecked(True)

    def disable(self):
        self.radiobuttons["NoScan"].setChecked(True)
        self.widgets["NoScan"].repetitions.setValue(1)

    @staticmethod
    def state_to_value(state):
        selected = state["selected"]
        r = dict(state[selected])
        r["ty"] = selected
        return r

    @staticmethod
    def default_state(procdesc):
        scale = procdesc["scale"]
        state = {
            "selected": "NoScan",
            "NoScan": {"value": 0.0, "repetitions": 1},
            "RangeScan": {"start": 0.0, "stop": 100.0*scale, "npoints": 10,
                          "randomize": False, "seed": None},
            "CenterScan": {"center": 0.*scale, "span": 100.*scale,
                           "step": 10.*scale, "randomize": False,
                           "seed": None},
            "ExplicitScan": {"sequence": []}
        }
        if "default" in procdesc:
            defaults = procdesc["default"]
            if not isinstance(defaults, list):
                defaults = [defaults]
            state["selected"] = defaults[0]["ty"]
            for default in reversed(defaults):
                ty = default["ty"]
                if ty == "NoScan":
                    state[ty]["value"] = default["value"]
                    state[ty]["repetitions"] = default["repetitions"]
                elif ty == "RangeScan":
                    state[ty]["start"] = default["start"]
                    state[ty]["stop"] = default["stop"]
                    state[ty]["npoints"] = default["npoints"]
                    state[ty]["randomize"] = default["randomize"]
                    state[ty]["seed"] = default["seed"]
                elif ty == "CenterScan":
                    for key in "center span step randomize seed".split():
                        state[ty][key] = default[key]
                elif ty == "ExplicitScan":
                    state[ty]["sequence"] = default["sequence"]
                else:
                    logger.warning("unknown default type: %s", ty)
        return state

    def _scan_type_toggled(self):
        for ty, button in self.radiobuttons.items():
            if button.isChecked():
                self.stack.setCurrentWidget(self.widgets[ty])
                self.argument["state"]["selected"] = ty
                break


def procdesc_to_entry(procdesc):
    ty = procdesc["ty"]
    if ty == "NumberValue":
        is_int = (procdesc["precision"] == 0
                  and int(procdesc["step"]) == procdesc["step"]
                  and procdesc["scale"] == 1)
        if is_int:
            return NumberEntryInt
        else:
            return NumberEntryFloat
    else:
        return {
            "PYONValue": StringEntry,
            "BooleanValue": BooleanEntry,
            "EnumerationValue": EnumerationEntry,
            "StringValue": StringEntry,
            "Scannable": ScanEntry
        }[ty]
