from collections import OrderedDict

from quamash import QtGui
import pyqtgraph as pg
from pyqtgraph import dockarea


class _BaseSettings(QtGui.QDialog):
    def __init__(self, parent, window_title, prev_name, create_cb):
        QtGui.QDialog.__init__(self, parent=parent)
        self.setWindowTitle(window_title)

        self.grid = QtGui.QGridLayout()
        self.setLayout(self.grid)

        self.grid.addWidget(QtGui.QLabel("Name:"), 0, 0)
        self.name = QtGui.QLineEdit()
        self.grid.addWidget(self.name, 0, 1)
        if prev_name is not None:
            self.name.setText(prev_name)

        def on_accept():
            create_cb(self.name.text(), self.get_input())
        self.accepted.connect(on_accept)

    def add_buttons(self):
        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        self.grid.addWidget(buttons, self.grid.rowCount(), 0, 1, 2)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def accept(self):
        if self.name.text() and self.validate_input():
            QtGui.QDialog.accept(self)

    def validate_input(self):
        raise NotImplementedError

    def get_input(self):
        raise NotImplementedError


class _SimpleSettings(_BaseSettings):
    def __init__(self, parent, prev_name, prev_settings,
                 result_list, create_cb):
        _BaseSettings.__init__(self, parent, self._window_title,
                               prev_name, create_cb)

        self.grid.addWidget(QtGui.QLabel("Result:"))
        self.result = QtGui.QComboBox()
        self.grid.addWidget(self.result, 1, 1)
        self.result.addItems(result_list)
        self.result.setEditable(True)
        if "result" in prev_settings:
            self.result.setEditText(prev_settings["result"])
        self.add_buttons()

    def validate_input(self):
        return bool(self.result.currentText())

    def get_input(self):
        return {"result": self.result.currentText()}


class NumberDisplaySettings(_SimpleSettings):
    _window_title = "Number display"


class NumberDisplay(dockarea.Dock):
    def __init__(self, name, settings):
        dockarea.Dock.__init__(self, "Display: " + name, size=(250, 250),
                               closable=True)
        self.settings = settings
        self.number = QtGui.QLCDNumber()
        self.number.setDigitCount(10)
        self.addWidget(self.number)

    def data_sources(self):
        return {self.settings["result"]}

    def update_data(self, data):
        result = self.settings["result"]
        try:
            n = float(data[result])
        except:
            n = "---"
        self.number.display(n)


class XYDisplaySettings(_SimpleSettings):
    _window_title = "XY plot"


class XYDisplay(dockarea.Dock):
    def __init__(self, name, settings):
        dockarea.Dock.__init__(self, "XY: " + name, size=(640, 480),
                               closable=True)
        self.settings = settings
        self.plot = pg.PlotWidget()
        self.addWidget(self.plot)

    def data_sources(self):
        return {self.settings["result"]}

    def update_data(self, data):
        result = self.settings["result"]
        try:
            y = data[result]
        except KeyError:
            return
        self.plot.clear()
        if not y:
            return
        self.plot.plot(y)


class HistogramDisplaySettings(_BaseSettings):
    def __init__(self, parent, prev_name, prev_settings,
                 result_list, create_cb):
        _BaseSettings.__init__(self, parent, "Histogram",
                               prev_name, create_cb)

        for row, axis in enumerate("yx"):
            self.grid.addWidget(QtGui.QLabel(axis.upper() + ":"))
            w = QtGui.QComboBox()
            self.grid.addWidget(w, row + 1, 1)
            if axis == "x":
                w.addItem("<None>")
            w.addItems(result_list)
            w.setEditable(True)
            if axis in prev_settings:
                w.setEditText(prev_settings["y"])
            setattr(self, axis, w)
        self.add_buttons()

    def validate_input(self):
        return bool(self.y.currentText()) and bool(self.x.currentText())

    def get_input(self):
        return {"y": self.y.currentText(), "x": self.x.currentText()}


class HistogramDisplay(dockarea.Dock):
    def __init__(self, name, settings):
        dockarea.Dock.__init__(self, "Histogram: " + name, size=(640, 480),
                               closable=True)
        self.settings = settings
        self.plot = pg.PlotWidget()
        self.addWidget(self.plot)

    def data_sources(self):
        s = {self.settings["y"]}
        if self.settings["x"] != "<None>":
            s.add(self.settings["x"])
        return s

    def update_data(self, data):
        result_y = self.settings["y"]
        result_x = self.settings["x"]
        try:
            y = data[result_y]
            if result_x == "<None>":
                x = None
            else:
                x = data[result_x]
        except KeyError:
            return
        if x is None:
            x = list(range(len(y)+1))

        if y and len(x) == len(y) + 1:
            self.plot.clear()
            self.plot.plot(x, y, stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))


display_types = OrderedDict([
    ("Number", (NumberDisplaySettings, NumberDisplay)),
    ("XY", (XYDisplaySettings, XYDisplay)),
    ("Histogram", (HistogramDisplaySettings, HistogramDisplay))
])
