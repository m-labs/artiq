from collections import OrderedDict
import numpy as np

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

        self.result_widgets = dict()
        for row, (has_none, key) in enumerate(self._result_keys):
            self.grid.addWidget(QtGui.QLabel(key.capitalize() + ":"))
            w = QtGui.QComboBox()
            self.grid.addWidget(w, row + 1, 1)
            if has_none:
                w.addItem("<None>")
            w.addItems(result_list)
            w.setEditable(True)
            if key in prev_settings:
                w.setEditText(prev_settings[key])
            self.result_widgets[key] = w
        self.add_buttons()

    def validate_input(self):
        return all(w.currentText() for w in self.result_widgets.values())

    def get_input(self):
        return {k: v.currentText() for k, v in self.result_widgets.items()}


class NumberDisplaySettings(_SimpleSettings):
    _window_title = "Number display"
    _result_keys = [(False, "result")]


class NumberDisplay(dockarea.Dock):
    def __init__(self, name, settings):
        dockarea.Dock.__init__(self, "Display: " + name, closable=True)
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

    def save_state(self):
        return None

    def restore_state(self, state):
        pass


class XYDisplaySettings(_SimpleSettings):
    _window_title = "XY plot"
    _result_keys = [(False, "y"), (True, "x"), (True, "error"), (True, "fit")]


class XYDisplay(dockarea.Dock):
    def __init__(self, name, settings):
        dockarea.Dock.__init__(self, "XY: " + name, closable=True)
        self.settings = settings
        self.plot = pg.PlotWidget()
        self.addWidget(self.plot)

    def data_sources(self):
        s = {self.settings["y"]}
        for k in "x", "error", "fit":
            if self.settings[k] != "<None>":
                s.add(self.settings[k])
        return s

    def update_data(self, data):
        result_y = self.settings["y"]
        result_x = self.settings["x"]
        result_error = self.settings["error"]
        result_fit = self.settings["fit"]

        try:
            y = data[result_y]
        except KeyError:
            return
        x = data.get(result_x, None)
        if x is None:
            x = list(range(len(y)))
        error = data.get(result_error, None)
        fit = data.get(result_fit, None)

        if not len(y) or len(y) != len(x):
            return
        if error is not None and hasattr(error, "__len__"):
            if not len(error):
                error = None
            elif len(error) != len(y):
                return
        if fit is not None:
            if not len(fit):
                fit = None
            elif len(fit) != len(y):
                return

        self.plot.clear()
        self.plot.plot(x, y, pen=None, symbol="x")
        if error is not None:
            # See https://github.com/pyqtgraph/pyqtgraph/issues/211
            if hasattr(error, "__len__") and not isinstance(error, np.ndarray):
                error = np.array(error)
            errbars = pg.ErrorBarItem(x=np.array(x), y=np.array(y), height=error)
            self.plot.addItem(errbars)
        if fit is not None:
            self.plot.plot(x, fit)

    def save_state(self):
        return self.plot.saveState()

    def restore_state(self, state):
        self.plot.restoreState(state)


class HistogramDisplaySettings(_SimpleSettings):
    _window_title = "Histogram"
    _result_keys = [(False, "y"), (True, "x")]


class HistogramDisplay(dockarea.Dock):
    def __init__(self, name, settings):
        dockarea.Dock.__init__(self, "Histogram: " + name, closable=True)
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

        if len(y) and len(x) == len(y) + 1:
            self.plot.clear()
            self.plot.plot(x, y, stepMode=True, fillLevel=0,
                           brush=(0, 0, 255, 150))

    def save_state(self):
        return self.plot.saveState()

    def restore_state(self, state):
        self.plot.restoreState(state)


display_types = OrderedDict([
    ("Number", (NumberDisplaySettings, NumberDisplay)),
    ("XY", (XYDisplaySettings, XYDisplay)),
    ("Histogram", (HistogramDisplaySettings, HistogramDisplay))
])
