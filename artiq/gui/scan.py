from quamash import QtGui
from pyqtgraph import LayoutWidget


class _Range(LayoutWidget):
    def __init__(self, global_min, global_max, global_step, unit, scale, ndecimals):
        LayoutWidget.__init__(self)

        self.scale = scale
        def apply_properties(spinbox):
            spinbox.setDecimals(ndecimals)
            if global_min is not None:
                spinbox.setMinimum(global_min/self.scale)
            else:
                spinbox.setMinimum(float("-inf"))
            if global_max is not None:
                spinbox.setMaximum(global_max/self.scale)
            else:
                spinbox.setMaximum(float("inf"))
            if global_step is not None:
                spinbox.setSingleStep(global_step/self.scale)
            if unit:
                spinbox.setSuffix(" " + unit)

        self.addWidget(QtGui.QLabel("Min:"), 0, 0)
        self.min = QtGui.QDoubleSpinBox()
        apply_properties(self.min)
        self.addWidget(self.min, 0, 1)

        self.addWidget(QtGui.QLabel("Max:"), 1, 0)
        self.max = QtGui.QDoubleSpinBox()
        apply_properties(self.max)
        self.addWidget(self.max, 1, 1)

        self.addWidget(QtGui.QLabel("#Points:"), 2, 0)
        self.npoints = QtGui.QSpinBox()
        self.npoints.setMinimum(2)
        self.npoints.setValue(10)
        self.addWidget(self.npoints, 2, 1)

    def set_values(self, min, max, npoints):
        self.min.setValue(min/self.scale)
        self.max.setValue(max/self.scale)
        self.npoints.setValue(npoints)

    def get_values(self):
        min = self.min.value()
        max = self.max.value()
        if min > max:
            raise ValueError("Minimum scan boundary must be less than maximum")
        return {
            "min": min*self.scale,
            "max": max*self.scale,
            "npoints": self.npoints.value()
        }


class ScanController(LayoutWidget):
    def __init__(self, procdesc):
        LayoutWidget.__init__(self)

        self.stack = QtGui.QStackedWidget()
        self.addWidget(self.stack, 1, 0, colspan=4)

        self.scale = procdesc["scale"]

        gmin, gmax = procdesc["global_min"], procdesc["global_max"]
        gstep = procdesc["global_step"]
        unit = procdesc["unit"]
        ndecimals = procdesc["ndecimals"]

        self.v_noscan = QtGui.QDoubleSpinBox()
        self.v_noscan.setDecimals(ndecimals)
        if gmin is not None:
            self.v_noscan.setMinimum(gmin/self.scale)
        else:
            self.v_noscan.setMinimum(float("-inf"))
        if gmax is not None:
            self.v_noscan.setMaximum(gmax/self.scale)
        else:
            self.v_noscan.setMaximum(float("inf"))
        self.v_noscan.setSingleStep(gstep/self.scale)
        if unit:
            self.v_noscan.setSuffix(" " + unit)
        self.v_noscan_gr = LayoutWidget()
        self.v_noscan_gr.addWidget(QtGui.QLabel("Value:"), 0, 0)
        self.v_noscan_gr.addWidget(self.v_noscan, 0, 1)
        self.stack.addWidget(self.v_noscan_gr)

        self.v_linear = _Range(gmin, gmax, gstep, unit, self.scale, ndecimals)
        self.stack.addWidget(self.v_linear)

        self.v_random = _Range(gmin, gmax, gstep, unit, self.scale, ndecimals)
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
            self.set_argument_value(procdesc["default"])
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
            return {"ty": "NoScan", "value": self.v_noscan.value()*self.scale}
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

    def set_argument_value(self, d):
        if d["ty"] == "NoScan":
            self.noscan.setChecked(True)
            self.v_noscan.setValue(d["value"]/self.scale)
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
            raise ValueError("Unknown scan type '{}'".format(d["ty"]))
