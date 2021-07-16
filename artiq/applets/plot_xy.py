#!/usr/bin/env python3

import numpy as np
import PyQt5  # make sure pyqtgraph imports Qt5
from PyQt5.QtCore import QTimer
import pyqtgraph

from artiq.applets.simple import TitleApplet


class XYPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        pyqtgraph.PlotWidget.__init__(self)
        self.args = args
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.length_warning)
        self.mismatch = {'X values': False,
                         'Error bars': False,
                         'Fit values': False}

    def data_changed(self, data, mods, title):
        try:
            y = data[self.args.y][1]
        except KeyError:
            return
        x = data.get(self.args.x, (False, None))[1]
        if x is None:
            x = np.arange(len(y))
        error = data.get(self.args.error, (False, None))[1]
        fit = data.get(self.args.fit, (False, None))[1]

        if not len(y) or len(y) != len(x):
            self.mismatch['X values'] = True
            self.timer.start(1000)
        else:
            self.mismatch['X values'] = False
            if not sum(self.mismatch.values()):
                self.timer.stop()
        if error is not None and hasattr(error, "__len__"):
            if not len(error):
                error = None
            elif len(error) != len(y):
                self.mismatch['Error bars'] = True
                self.timer.start(1000)
            else:
                self.mismatch['Error bars'] = False
                if not sum(self.mismatch.values()):
                    self.timer.stop()
        if fit is not None:
            if not len(fit):
                fit = None
            elif len(fit) != len(y):
                self.mismatch['Fit values'] = True
                self.timer.start(1000)
            else:
                self.mismatch['Fit values'] = False
                if not sum(self.mismatch.values()):
                    self.timer.stop()

        self.clear()
        if self.mismatch['X values']:
            return
        self.plot(x, y, pen=None, symbol="x")
        self.setTitle(title)
        if error is not None and not self.mismatch['Error bars']:
            # See https://github.com/pyqtgraph/pyqtgraph/issues/211
            if hasattr(error, "__len__") and not isinstance(error, np.ndarray):
                error = np.array(error)
            errbars = pyqtgraph.ErrorBarItem(
                x=np.array(x), y=np.array(y), height=error)
            self.addItem(errbars)
        if fit is not None and not self.mismatch['Fit values']:
            xi = np.argsort(x)
            self.plot(x[xi], fit[xi])

    def length_warning(self):
        text = "⚠️ dataset lengths mismatch:\n"
        for key in self.mismatch:
            if self.mismatch[key]:
                text += key + ', '
        text += "should have the same length as Y values"
        self.addItem(pyqtgraph.TextItem(text))


def main():
    applet = TitleApplet(XYPlot)
    applet.add_dataset("y", "Y values")
    applet.add_dataset("x", "X values", required=False)
    applet.add_dataset("error", "Error bars for each X value", required=False)
    applet.add_dataset("fit", "Fit values for each X value", required=False)
    applet.run()

if __name__ == "__main__":
    main()
