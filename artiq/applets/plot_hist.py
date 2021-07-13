#!/usr/bin/env python3

import PyQt5    # make sure pyqtgraph imports Qt5
from PyQt5.QtCore import QTimer
import pyqtgraph

from artiq.applets.simple import TitleApplet


class HistogramPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        pyqtgraph.PlotWidget.__init__(self)
        self.args = args
        self.timer = QTimer()
        self.timer.timeout.connect(self.warning)

    def data_changed(self, data, mods, title):
        try:
            self.y = data[self.args.y][1]
            if self.args.x is None:
                self.x = None
            else:
                self.x = data[self.args.x][1]
        except KeyError:
            return
        if self.x is None:
            self.x = list(range(len(self.y)+1))

        if len(self.y) and len(self.x) == len(self.y) + 1:
            self.clear()
            self.plot(self.x, self.y, stepMode=True, fillLevel=0,
                      brush=(0, 0, 255, 150))
            self.setTitle(title)
        else:
            self.timer.start(1000)

    def warning(self):
        if len(self.y) and len(self.x) == len(self.y) + 1:
            return
        else:
            self.timer.stop()
            self.clear()
            text = '''⚠️ dataset lengths mismatch:\n
                      BIN_BOUNDARIES should be one more than COUNTS'''
            self.addItem(pyqtgraph.TextItem(text))


def main():
    applet = TitleApplet(HistogramPlot)
    applet.add_dataset("y", "Y values")
    applet.add_dataset("x", "Bin boundaries", required=False)
    applet.run()

if __name__ == "__main__":
    main()
