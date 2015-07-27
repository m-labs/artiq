from quamash import QtGui
from pyqtgraph import LayoutWidget

from artiq.gui.tools import force_spinbox_value


class _Range(LayoutWidget):
    def __init__(self, global_min, global_max, global_step, unit):
        LayoutWidget.__init__(self)

        def apply_properties(spinbox):
            if global_min is not None:
                spinbox.setMinimum(global_min)
            if global_max is not None:
                spinbox.setMaximum(global_max)
            if global_step is not None:
                spinbox.setSingleStep(global_step)
            if unit:
                spinbox.setSuffix(" " + unit)

        self.addWidget(QtGui.QLabel("Min:"), 0, 0)
        self.min = QtGui.QDoubleSpinBox()
        apply_properties(self.min)
        self.addWidget(self.min, 0, 1)

        self.addWidget(QtGui.QLabel("Max:"), 0, 2)
        self.max = QtGui.QDoubleSpinBox()
        apply_properties(self.max)
        self.addWidget(self.max, 0, 3)

        self.addWidget(QtGui.QLabel("#Points:"), 0, 4)
        self.npoints = QtGui.QSpinBox()
        self.npoints.setMinimum(2)
        self.npoints.setValue(10)
        self.addWidget(self.npoints, 0, 5)

    def set_values(self, min, max, npoints):
        force_spinbox_value(self.min, min)
        force_spinbox_value(self.max, max)
        force_spinbox_value(self.npoints, npoints)

    def get_values(self):
        return {
            "min": self.min.value(),
            "max": self.max.value(),
            "npoints": self.npoints.value()
        }


class ScanController(LayoutWidget):
    def __init__(self, procdesc):
        LayoutWidget.__init__(self)

        self.stack = QtGui.QStackedWidget()
        self.addWidget(self.stack, 1, 0, colspan=4)

        gmin, gmax = procdesc["global_min"], procdesc["global_max"]
        gstep = procdesc["global_step"]
        unit = procdesc["unit"]

        self.v_noscan = QtGui.QDoubleSpinBox()
        if gmin is not None:
            self.v_noscan.setMinimum(gmin)
        if gmax is not None:
            self.v_noscan.setMaximum(gmax)
        if gstep is not None:
            self.v_noscan.setSingleStep(gstep)
        if unit:
            self.v_noscan.setSuffix(" " + unit)
        self.v_noscan_gr = LayoutWidget()
        self.v_noscan_gr.addWidget(QtGui.QLabel("Value:"), 0, 0)
        self.v_noscan_gr.addWidget(self.v_noscan, 0, 1)
        self.stack.addWidget(self.v_noscan_gr)

        self.v_linear = _Range(gmin, gmax, gstep, unit)
        self.stack.addWidget(self.v_linear)

        self.v_random = _Range(gmin, gmax, gstep, unit)
        self.stack.addWidget(self.v_random)

        self.v_explicit = QtGui.QLineEdit()
        self.v_explicit_gr = LayoutWidget()
        self.v_explicit_gr.addWidget(QtGui.QLabel("Sequence:"), 0, 0)
        self.v_explicit_gr.addWidget(self.v_explicit, 0, 1)
        self.stack.addWidget(self.v_explicit_gr)

        self.noscan = QtGui.QRadioButton("No scan")
        self.linear = QtGui.QRadioButton("Linear")
        self.random = QtGui.QRadioButton("Random")
        self.explicit = QtGui.QRadioButton("Explicit")
        radiobuttons = QtGui.QButtonGroup()
        for n, b in enumerate([self.noscan, self.linear,
                               self.random, self.explicit]):
            self.addWidget(b, 0, n)
            radiobuttons.addButton(b)
            b.toggled.connect(self.select_page)

        if "default" in procdesc:
            d = procdesc["default"]
            if d["ty"] == "NoScan":
                self.noscan.setChecked(True)
                force_spinbox_value(self.v_noscan, d["value"])
            elif d["ty"] == "LinearScan":
                self.linear.setChecked(True)
                self.v_linear.set_values(d["min"], d["max"], d["npoints"])
            elif d["ty"] == "RandomScan":
                self.random.setChecked(True)
                self.v_random.set_values(d["min"], d["max"], d["npoints"])
            elif d["ty"] == "ExplicitScan":
                self.explicit.setChecked(True)
                self.v_explicit.insert(" ".join(
                    [str(x) for x in d["sequence"]]))
        else:
            self.noscan.setChecked(True)

    def select_page(self):
        if self.noscan.isChecked():
            self.stack.setCurrentWidget(self.v_noscan_gr)
        elif self.linear.isChecked():
            self.stack.setCurrentWidget(self.v_linear)
        elif self.random.isChecked():
            self.stack.setCurrentWidget(self.v_random)
        elif self.explicit.isChecked():
            self.stack.setCurrentWidget(self.v_explicit_gr)

    def get_argument_value(self):
        if self.noscan.isChecked():
            return {"ty": "NoScan", "value": self.v_noscan.value()}
        elif self.linear.isChecked():
            d = {"ty": "LinearScan"}
            d.update(self.v_linear.get_values())
            return d
        elif self.random.isChecked():
            d = {"ty": "RandomScan"}
            d.update(self.v_random.get_values())
            return d
        elif self.explicit.isChecked():
            sequence = [float(x) for x in self.v_explicit.text().split()]
            return {"ty": "ExplicitScan", "sequence": sequence}
