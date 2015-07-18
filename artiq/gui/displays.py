from collections import OrderedDict

from quamash import QtGui
import pyqtgraph as pg
from pyqtgraph import dockarea


class _SimpleSettings(QtGui.QDialog):
    def __init__(self, parent, prev_name, prev_settings,
                 result_list, create_cb):
        QtGui.QDialog.__init__(self, parent=parent)
        self.setWindowTitle(self._window_title)

        grid = QtGui.QGridLayout()
        self.setLayout(grid)

        grid.addWidget(QtGui.QLabel("Name:"), 0, 0)
        self.name = name = QtGui.QLineEdit()
        grid.addWidget(name, 0, 1)
        if prev_name is not None:
            name.insert(prev_name)

        grid.addWidget(QtGui.QLabel("Result:"))
        self.result = result = QtGui.QComboBox()
        grid.addWidget(result, 1, 1)
        result.addItems(result_list)
        result.setEditable(True)
        if "result" in prev_settings:
            result.setEditText(prev_settings["result"])

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        grid.addWidget(buttons, 2, 0, 1, 2)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        def on_accept():
            create_cb(name.text(), {"result": result.currentText()})
        self.accepted.connect(on_accept)

    def accept(self):
        if self.name.text() and self.result.currentText():
            QtGui.QDialog.accept(self)


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


class HistogramDisplaySettings(_SimpleSettings):
    _window_title = "Histogram"


class HistogramDisplay(dockarea.Dock):
    def __init__(self, name, settings):
        dockarea.Dock.__init__(self, "Histogram: " + name, size=(640, 480),
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
        x = list(range(len(y)+1))
        self.plot.clear()
        if not y:
            return
        self.plot.plot(x, y, stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))


display_types = OrderedDict([
    ("Number", (NumberDisplaySettings, NumberDisplay)),
    ("XY", (XYDisplaySettings, XYDisplay)),
    ("Histogram", (HistogramDisplaySettings, HistogramDisplay))
])
