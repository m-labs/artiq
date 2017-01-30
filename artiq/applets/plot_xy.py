#!/usr/bin/env python3

import numpy as np
import PyQt5  # make sure pyqtgraph imports Qt5
import pyqtgraph

from artiq.applets.simple import TitleApplet


class XYPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        pyqtgraph.PlotWidget.__init__(self)
        self.args = args

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

        self.clear()
        self.plot(x, y, pen=None, symbol="x")
        self.setTitle(title)
        if error is not None:
            # See https://github.com/pyqtgraph/pyqtgraph/issues/211
            if hasattr(error, "__len__") and not isinstance(error, np.ndarray):
                error = np.array(error)
            errbars = pyqtgraph.ErrorBarItem(
                x=np.array(x), y=np.array(y), height=error)
            self.addItem(errbars)
        if fit is not None:
            xi = np.argsort(x)
            self.plot(x[xi], fit[xi])


def main():
    applet = TitleApplet(XYPlot)
    applet.add_dataset("y", "Y values")
    applet.add_dataset("x", "X values", required=False)
    applet.add_dataset("error", "Error bars for each X value", required=False)
    applet.add_dataset("fit", "Fit values for each X value", required=False)
    applet.run()

if __name__ == "__main__":
    main()
