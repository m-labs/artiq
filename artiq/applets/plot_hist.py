#!/usr/bin/env python3

import PyQt5    # make sure pyqtgraph imports Qt5
from PyQt5.QtCore import QTimer
import pyqtgraph

from artiq.applets.simple import TitleApplet


class HistogramPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        pyqtgraph.PlotWidget.__init__(self)
        self.args = args
        self.flag = True
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.length_warning)

    def data_changed(self, data, mods, title):
        try:
            y = data[self.args.y][1]
            if self.args.x is None:
                x = None
            else:
                x = data[self.args.x][1]
        except KeyError:
            return
        if x is None:
            x = list(range(len(y)+1))

        if len(y) and len(x) == len(y) + 1:
            self.flag = True
            self.timer.stop()
            self.clear()
            self.plot(x, y, stepMode=True, fillLevel=0,
                      brush=(0, 0, 255, 150))
            self.setTitle(title)
        else:
            if self.flag:
                self.flag = False
                self.clear()
                self.timer.start(1000)

    def length_warning(self):
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
