import logging
from collections import OrderedDict

from quamash import QtGui, QtCore
from pyqtgraph import LayoutWidget

from artiq.gui.tools import disable_scroll_wheel


logger = logging.getLogger(__name__)


class _NoScan(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        scale = procdesc["scale"]
        self.value = QtGui.QDoubleSpinBox()
        disable_scroll_wheel(self.value)
        self.value.setDecimals(procdesc["ndecimals"])
        if procdesc["global_min"] is not None:
            self.value.setMinimum(procdesc["global_min"]/scale)
        else:
            self.value.setMinimum(float("-inf"))
        if procdesc["global_max"] is not None:
            self.value.setMaximum(procdesc["global_max"]/scale)
        else:
            self.value.setMaximum(float("inf"))
        self.value.setSingleStep(procdesc["global_step"]/scale)
        if procdesc["unit"]:
            self.value.setSuffix(" " + procdesc["unit"])
        self.addWidget(QtGui.QLabel("Value:"), 0, 0)
        self.addWidget(self.value, 0, 1)

        self.value.setValue(state["value"]/scale)
        def update(value):
            state["value"] = value*scale
        self.value.valueChanged.connect(update)


class _Range(LayoutWidget):
    def __init__(self, procdesc, state):
        LayoutWidget.__init__(self)

        scale = procdesc["scale"]
        def apply_properties(spinbox):
            spinbox.setDecimals(procdesc["ndecimals"])
            if procdesc["global_min"] is not None:
                spinbox.setMinimum(procdesc["global_min"]/scale)
            else:
                spinbox.setMinimum(float("-inf"))
            if procdesc["global_max"] is not None:
                spinbox.setMaximum(procdesc["global_max"]/scale)
            else:
                spinbox.setMaximum(float("inf"))
            if procdesc["global_step"] is not None:
                spinbox.setSingleStep(procdesc["global_step"]/scale)
            if procdesc["unit"]:
                spinbox.setSuffix(" " + procdesc["unit"])

        self.addWidget(QtGui.QLabel("Min:"), 0, 0)
        self.min = QtGui.QDoubleSpinBox()
        disable_scroll_wheel(self.min)
        apply_properties(self.min)
        self.addWidget(self.min, 0, 1)

        self.addWidget(QtGui.QLabel("Max:"), 1, 0)
        self.max = QtGui.QDoubleSpinBox()
        disable_scroll_wheel(self.max)
        apply_properties(self.max)
        self.addWidget(self.max, 1, 1)

        self.addWidget(QtGui.QLabel("#Points:"), 2, 0)
        self.npoints = QtGui.QSpinBox()
        disable_scroll_wheel(self.npoints)
        self.npoints.setMinimum(2)
        self.npoints.setValue(10)
        self.addWidget(self.npoints, 2, 1)

        self.min.setValue(state["min"]/scale)
        self.max.setValue(state["max"]/scale)
        self.npoints.setValue(state["npoints"])
        def update_min(value):
            state["min"] = value*scale
        def update_max(value):
            state["min"] = value*scale
        def update_npoints(value):
            state["npoints"] = value
        self.min.valueChanged.connect(update_min)
        self.max.valueChanged.connect(update_max)
        self.npoints.valueChanged.connect(update_npoints)

class _Explicit(LayoutWidget):
    def __init__(self, state):
        LayoutWidget.__init__(self)

        self.value = QtGui.QLineEdit()
        self.addWidget(QtGui.QLabel("Sequence:"), 0, 0)
        self.addWidget(self.value, 0, 1)

        float_regexp = "[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?"
        regexp = "(float)?( +float)* *".replace("float", float_regexp)
        self.value.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp(regexp),
                                                       self.value))

        self.value.setText(" ".join([str(x) for x in state["sequence"]]))
        def update(text):
            state["sequence"] = [float(x) for x in text.split()]
        self.value.textEdited.connect(update)


class ScanController(LayoutWidget):
    def __init__(self, argument):
        LayoutWidget.__init__(self)
        self.argument = argument

        self.stack = QtGui.QStackedWidget()
        self.addWidget(self.stack, 1, 0, colspan=4)

        procdesc = argument["desc"]
        state = argument["state"]
        self.widgets = OrderedDict()
        self.widgets["NoScan"] = _NoScan(procdesc, state["NoScan"])
        self.widgets["LinearScan"] = _Range(procdesc, state["LinearScan"])
        self.widgets["RandomScan"] = _Range(procdesc, state["RandomScan"])
        self.widgets["ExplicitScan"] = _Explicit(state["ExplicitScan"])
        for widget in self.widgets.values():
            self.stack.addWidget(widget)

        self.radiobuttons = OrderedDict()
        self.radiobuttons["NoScan"] = QtGui.QRadioButton("No scan")
        self.radiobuttons["LinearScan"] = QtGui.QRadioButton("Linear")
        self.radiobuttons["RandomScan"] = QtGui.QRadioButton("Random")
        self.radiobuttons["ExplicitScan"] = QtGui.QRadioButton("Explicit")
        scan_type = QtGui.QButtonGroup()
        for n, b in enumerate(self.radiobuttons.values()):
            self.addWidget(b, 0, n)
            scan_type.addButton(b)
            b.toggled.connect(self._scan_type_toggled)

        selected = argument["state"]["selected"]
        self.radiobuttons[selected].setChecked(True)

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
            "NoScan": {"value": 0.0},
            "LinearScan": {"min": 0.0, "max": 100.0*scale, "npoints": 10},
            "RandomScan": {"min": 0.0, "max": 100.0*scale, "npoints": 10},
            "ExplicitScan": {"sequence": []}
        }
        if "default" in procdesc:
            default = procdesc["default"]
            ty = default["ty"]
            state["selected"] = ty
            if ty == "NoScan":
                state["NoScan"]["value"] = default["value"]
            elif ty == "LinearScan" or ty == "RandomScan":
                for d in state["LinearScan"], state["RandomScan"]:
                    d["min"] = default["min"]
                    d["max"] = default["max"]
                    d["npoints"] = default["npoints"]
            elif ty == "ExplicitScan":
                state["ExplicitScan"]["sequence"] = default["sequence"]
            else:
                logger.warning("unknown default type: %s", ty)
        return state

    def _scan_type_toggled(self):
        for ty, button in self.radiobuttons.items():
            if button.isChecked():
                self.stack.setCurrentWidget(self.widgets[ty])
                self.argument["state"]["selected"] = ty
                break
