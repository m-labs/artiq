import logging
from collections import OrderedDict

from PyQt5 import QtCore, QtGui, QtWidgets

from artiq.gui.tools import LayoutWidget, disable_scroll_wheel
from artiq.gui.scanwidget import ScanWidget
from artiq.gui.scientific_spinbox import ScientificSpinBox


logger = logging.getLogger(__name__)


class StringEntry(QtWidgets.QLineEdit):
    def __init__(self, argument):
        QtWidgets.QLineEdit.__init__(self)
        self.argument = argument
        self.update_state()
        def update(text):
            self.argument["state"] = text
        self.textEdited.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        return procdesc.get("default", "")

    def update_state(self):
        with QtCore.QSignalBlocker(self):
            self.setText(self.argument["state"])


class BooleanEntry(QtWidgets.QCheckBox):
    def __init__(self, argument):
        QtWidgets.QCheckBox.__init__(self)
        self.argument = argument
        self.update_state()
        def update(checked):
            self.argument["state"] = bool(checked)
        self.stateChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        return procdesc.get("default", False)

    def update_state(self):
        with QtCore.QSignalBlocker(self):
            self.setChecked(self.argument["state"])


class EnumerationEntry(QtWidgets.QComboBox):
    def __init__(self, argument):
        QtWidgets.QComboBox.__init__(self)
        disable_scroll_wheel(self)
        self.argument = argument
        self.choices = argument["desc"]["choices"]
        self.addItems(self.choices)
        self.update_state()
        def update(index):
            self.argument["state"] = self.choices[index]
        self.currentIndexChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        if "default" in procdesc:
            return procdesc["default"]
        else:
            return procdesc["choices"][0]

    def update_state(self):
        with QtCore.QSignalBlocker(self):
            state = self.argument["state"]
            if state in self.choices:
                self.setCurrentIndex(self.choices.index(state))
            else:
                raise ValueError("Invalid EnumerationValue value")


class NumberEntryInt(QtWidgets.QSpinBox):
    def __init__(self, argument):
        QtWidgets.QSpinBox.__init__(self)
        disable_scroll_wheel(self)
        self.argument = argument
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

        self.update_state()
        def update(value):
            self.argument["state"] = value
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

    def update_state(self):
        with QtCore.QSignalBlocker(self):
            self.setValue(self.argument["state"])


class NumberEntryFloat(ScientificSpinBox):
    def __init__(self, argument):
        ScientificSpinBox.__init__(self)
        disable_scroll_wheel(self)
        self.argument = argument
        procdesc = argument["desc"]
        self.scale = procdesc["scale"]
        self.setDecimals(procdesc["precision"])
        self.setSigFigs()
        self.setSingleStep(procdesc["step"]/self.scale)
        self.setRelativeStep()
        if procdesc["min"] is not None:
            self.setMinimum(procdesc["min"]/self.scale)
        else:
            self.setMinimum(float("-inf"))
        if procdesc["max"] is not None:
            self.setMaximum(procdesc["max"]/self.scale)
        else:
            self.setMaximum(float("inf"))
        if procdesc["unit"]:
            self.setSuffix(" " + procdesc["unit"])

        self.update_state()
        def update(value):
            argument["state"] = value*self.scale
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

    def update_state(self):
        with QtCore.QSignalBlocker(self):
            self.setValue(self.argument["state"]/self.scale)


class _NoScan(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        self.scale = procdesc["scale"]
        self.value = ScientificSpinBox()
        disable_scroll_wheel(self.value)
        self.value.setDecimals(procdesc["precision"])
        self.value.setSigFigs()
        if procdesc["global_min"] is not None:
            self.value.setMinimum(procdesc["global_min"]/self.scale)
        else:
            self.value.setMinimum(float("-inf"))
        if procdesc["global_max"] is not None:
            self.value.setMaximum(procdesc["global_max"]/self.scale)
        else:
            self.value.setMaximum(float("inf"))
        self.value.setSingleStep(procdesc["global_step"]/self.scale)
        self.value.setRelativeStep()
        if procdesc["unit"]:
            self.value.setSuffix(" " + procdesc["unit"])
        self.addWidget(QtWidgets.QLabel("Value:"), 0, 0)
        self.addWidget(self.value, 0, 1)

        def update(value):
            state["value"] = value*self.scale
        self.value.valueChanged.connect(update)

        self.repetitions = QtWidgets.QSpinBox()
        self.repetitions.setMinimum(1)
        self.repetitions.setMaximum((1 << 31) - 1)
        disable_scroll_wheel(self.repetitions)
        self.addWidget(QtWidgets.QLabel("Repetitions:"), 1, 0)
        self.addWidget(self.repetitions, 1, 1)

        self.update_state(state)
        def update_repetitions(value):
            state["repetitions"] = value
        self.repetitions.valueChanged.connect(update_repetitions)

    def update_state(self, state):
        with QtCore.QSignalBlocker(self):
            self.value.setValue(state["value"]/self.scale)
            self.repetitions.setValue(state["repetitions"])


class _RangeScan(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        self.scale = procdesc["scale"]

        def apply_properties(widget):
            widget.setDecimals(procdesc["precision"])
            if procdesc["global_min"] is not None:
                widget.setMinimum(procdesc["global_min"]/self.scale)
            else:
                widget.setMinimum(float("-inf"))
            if procdesc["global_max"] is not None:
                widget.setMaximum(procdesc["global_max"]/self.scale)
            else:
                widget.setMaximum(float("inf"))
            if procdesc["global_step"] is not None:
                widget.setSingleStep(procdesc["global_step"]/self.scale)
            if procdesc["unit"]:
                widget.setSuffix(" " + procdesc["unit"])

        scanner = ScanWidget()
        disable_scroll_wheel(scanner)
        self.addWidget(scanner, 0, 0, -1, 1)

        self.start = ScientificSpinBox()
        self.start.setStyleSheet("QDoubleSpinBox {color:blue}")
        self.start.setMinimumSize(110, 0)
        self.start.setSizePolicy(QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed))
        disable_scroll_wheel(self.start)
        self.addWidget(self.start, 0, 1)

        self.npoints = QtWidgets.QSpinBox()
        self.npoints.setMinimum(1)
        self.npoints.setMaximum((1 << 31) - 1)
        disable_scroll_wheel(self.npoints)
        self.addWidget(self.npoints, 1, 1)

        self.stop = ScientificSpinBox()
        self.stop.setStyleSheet("QDoubleSpinBox {color:red}")
        self.stop.setMinimumSize(110, 0)
        disable_scroll_wheel(self.stop)
        self.addWidget(self.stop, 2, 1)

        self.randomize = QtWidgets.QCheckBox("Randomize")
        self.addWidget(self.randomize, 3, 1)

        apply_properties(self.start)
        self.start.setSigFigs()
        self.start.setRelativeStep()
        apply_properties(self.stop)
        self.stop.setSigFigs()
        self.stop.setRelativeStep()
        apply_properties(scanner)

        self.update_state(state)
        def update_start(value):
            state["start"] = value*self.scale
            scanner.setStart(value)
            if self.start.value() != value:
                self.start.setValue(value)

        def update_stop(value):
            state["stop"] = value*self.scale
            scanner.setStop(value)
            if self.stop.value() != value:
                self.stop.setValue(value)

        def update_npoints(value):
            state["npoints"] = value
            scanner.setNum(value)
            if self.npoints.value() != value:
                self.npoints.setValue(value)

        def update_randomize(value):
            state["randomize"] = value
            self.randomize.setChecked(value)

        scanner.startChanged.connect(update_start)
        scanner.numChanged.connect(update_npoints)
        scanner.stopChanged.connect(update_stop)
        self.start.valueChanged.connect(update_start)
        self.npoints.valueChanged.connect(update_npoints)
        self.stop.valueChanged.connect(update_stop)
        self.randomize.stateChanged.connect(update_randomize)
        scanner.setStart(state["start"]/self.scale)
        scanner.setNum(state["npoints"])
        scanner.setStop(state["stop"]/self.scale)
        self.randomize.setChecked(state["randomize"])

    def update_state(self, state):
        with QtCore.QSignalBlocker(self):
            self.start.setValue(state["start"]/self.scale)
            self.npoints.setValue(state["npoints"])
            self.stop.setValue(state["stop"]/self.scale)
            self.randomize.setChecked(state["randomize"])


class _CenterScan(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        self.scale = procdesc["scale"]

        def apply_properties(widget):
            widget.setDecimals(procdesc["precision"])
            if procdesc["global_min"] is not None:
                widget.setMinimum(procdesc["global_min"]/self.scale)
            else:
                widget.setMinimum(float("-inf"))
            if procdesc["global_max"] is not None:
                widget.setMaximum(procdesc["global_max"]/self.scale)
            else:
                widget.setMaximum(float("inf"))
            if procdesc["global_step"] is not None:
                widget.setSingleStep(procdesc["global_step"]/self.scale)
            if procdesc["unit"]:
                widget.setSuffix(" " + procdesc["unit"])

        self.center = ScientificSpinBox()
        disable_scroll_wheel(self.center)
        apply_properties(self.center)
        self.center.setSigFigs()
        self.center.setRelativeStep()
        self.addWidget(self.center, 0, 1)
        self.addWidget(QtWidgets.QLabel("Center:"), 0, 0)

        self.span = ScientificSpinBox()
        disable_scroll_wheel(self.span)
        apply_properties(self.span)
        self.span.setSigFigs()
        self.span.setRelativeStep()
        self.span.setMinimum(0)
        self.addWidget(self.span, 1, 1)
        self.addWidget(QtWidgets.QLabel("Span:"), 1, 0)

        self.step = ScientificSpinBox()
        disable_scroll_wheel(self.step)
        apply_properties(self.step)
        self.step.setSigFigs()
        self.step.setRelativeStep()
        self.step.setMinimum(0)
        self.addWidget(self.step, 2, 1)
        self.addWidget(QtWidgets.QLabel("Step:"), 2, 0)

        self.randomize = QtWidgets.QCheckBox("Randomize")
        self.addWidget(self.randomize, 3, 1)

        self.update_state(state)
        def update_center(value):
            state["center"] = value*self.scale

        def update_span(value):
            state["span"] = value*self.scale

        def update_step(value):
            state["step"] = value*self.scale

        def update_randomize(value):
            state["randomize"] = value

        self.center.valueChanged.connect(update_center)
        self.span.valueChanged.connect(update_span)
        self.step.valueChanged.connect(update_step)
        self.randomize.stateChanged.connect(update_randomize)

    def update_state(self, state):
        with QtCore.QSignalBlocker(self):
            self.center.setValue(state["center"]/self.scale)
            self.span.setValue(state["span"]/self.scale)
            self.step.setValue(state["step"]/self.scale)
            self.randomize.setChecked(state["randomize"])


class _ExplicitScan(LayoutWidget):
    def __init__(self, state):
        LayoutWidget.__init__(self)

        self.value = QtWidgets.QLineEdit()
        self.addWidget(QtWidgets.QLabel("Sequence:"), 0, 0)
        self.addWidget(self.value, 0, 1)

        float_regexp = r"(([+-]?\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)"
        regexp = "(float)?( +float)* *".replace("float", float_regexp)
        self.value.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp(regexp)))

        self.update_state(state)
        def update(text):
            if self.value.hasAcceptableInput():
                state["sequence"] = [float(x) for x in text.split()]
        self.value.textEdited.connect(update)

    def update_state(self, state):
        with QtCore.QSignalBlocker(self):
            self.value.setText(" ".join([str(x) for x in state["sequence"]]))

    
class ScanEntry(LayoutWidget):
    def __init__(self, argument):
        LayoutWidget.__init__(self)
        self.argument = argument

        self.stack = QtWidgets.QStackedWidget()
        self.addWidget(self.stack, 1, 0, colspan=4)

        procdesc = argument["desc"]
        self.state = argument["state"]
        self.widgets = OrderedDict()
        self.widgets["NoScan"] = _NoScan(procdesc, self.state["NoScan"])
        self.widgets["RangeScan"] = _RangeScan(procdesc, self.state["RangeScan"])
        self.widgets["CenterScan"] = _CenterScan(procdesc, self.state["CenterScan"])
        self.widgets["ExplicitScan"] = _ExplicitScan(self.state["ExplicitScan"])
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
        self.update_state()

    def disable(self):
        self.radiobuttons["NoScan"].setChecked(True)
        self.widgets["NoScan"].repetitions.setValue(1)

    def update_state(self):
        with QtCore.QSignalBlocker(self):
            for ty in ["NoScan", "RangeScan", "CenterScan", "ExplicitScan"]:
                self.widgets[ty].update_state(self.state[ty])
            self.radiobuttons[self.state["selected"]].setChecked(True)

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
