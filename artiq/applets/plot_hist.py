#!/usr/bin/env python3

import PyQt5  # make sure pyqtgraph imports Qt5
import pyqtgraph

from artiq.applets.simple import TitleApplet


class HistogramPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        pyqtgraph.PlotWidget.__init__(self)
        self.args = args

    def data_changed(self, data, mods, title):
        if not hasattr(self, 'flag'):
            self.flag = True

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
            self.clear()
            self.plot(x, y, stepMode=True, fillLevel=0,
                      brush=(0, 0, 255, 150))
            self.setTitle(title)
        else:
            if self.flag:
                self.flag_time = pyqtgraph.ptime.time()
            self.flag = False
            if pyqtgraph.ptime.time() - self.flag_time > 0.5:
                self.clear()
                text = '⚠️ The length of dataset X is not Y+1'
                self.addItem(pyqtgraph.TextItem(text))


def main():
    applet = TitleApplet(HistogramPlot)
    applet.add_dataset("y", "Y values")
    applet.add_dataset("x", "Bin boundaries", required=False)
    applet.run()

if __name__ == "__main__":
    main()
