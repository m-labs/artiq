#!/usr/bin/env python3

import numpy as np
from PyQt5 import QtWidgets
import pyqtgraph

from artiq.applets.simple import SimpleApplet


def _compute_ys(histogram_bins, histograms_counts):
        bin_centers = np.empty(len(histogram_bins)-1)
        for i in range(len(bin_centers)):
            bin_centers[i] = (histogram_bins[i] + histogram_bins[i+1])/2

        ys = np.empty(histograms_counts.shape[0])
        for n, counts in enumerate(histograms_counts):
            ys[n] = sum(bin_centers*counts)/sum(counts)
        return ys


# pyqtgraph.GraphicsWindow fails to behave like a regular Qt widget
# and breaks embedding. Do not use as top widget.
class XYHistPlot(QtWidgets.QSplitter):
    def __init__(self, args):
        QtWidgets.QSplitter.__init__(self)
        self.resize(1000, 600)
        self.setWindowTitle("XY/Histogram")

        self.xy_plot = pyqtgraph.PlotWidget()
        self.insertWidget(0, self.xy_plot)
        self.xy_plot_data = None
        self.arrow = None
        self.selected_index = None

        self.hist_plot = pyqtgraph.PlotWidget()
        self.insertWidget(1, self.hist_plot)
        self.hist_plot_data = None

        self.args = args

    def _set_full_data(self, xs, histogram_bins, histograms_counts):
        self.xy_plot.clear()
        self.hist_plot.clear()
        self.xy_plot_data = None
        self.hist_plot_data = None
        self.arrow = None
        self.selected_index = None

        self.histogram_bins = histogram_bins

        ys = _compute_ys(self.histogram_bins, histograms_counts)
        self.xy_plot_data = self.xy_plot.plot(x=xs, y=ys,
                                              pen=None,
                                              symbol="x", symbolSize=20)
        self.xy_plot_data.sigPointsClicked.connect(self._point_clicked)
        for index, (point, counts) in (
                enumerate(zip(self.xy_plot_data.scatter.points(),
                              histograms_counts))):
            point.histogram_index = index
            point.histogram_counts = counts

        self.hist_plot_data = self.hist_plot.plot(
            stepMode=True, fillLevel=0,
            brush=(0, 0, 255, 150))

    def _set_partial_data(self, xs, histograms_counts):
        ys = _compute_ys(self.histogram_bins, histograms_counts)
        self.xy_plot_data.setData(x=xs, y=ys,
                                  pen=None,
                                  symbol="x", symbolSize=20)
        for index, (point, counts) in (
                enumerate(zip(self.xy_plot_data.scatter.points(),
                              histograms_counts))):
            point.histogram_index = index
            point.histogram_counts = counts

    def _point_clicked(self, data_item, spot_items):
        spot_item = spot_items[0]
        position = spot_item.pos()
        if self.arrow is None:
            self.arrow = pyqtgraph.ArrowItem(
                angle=-120, tipAngle=30, baseAngle=20, headLen=40,
                tailLen=40, tailWidth=8, pen=None, brush="y")
            self.arrow.setPos(position)
            # NB: temporary glitch if addItem is done before setPos
            self.xy_plot.addItem(self.arrow)
        else:
            self.arrow.setPos(position)
        self.selected_index = spot_item.histogram_index
        self.hist_plot_data.setData(x=self.histogram_bins,
                                    y=spot_item.histogram_counts)

    def _can_use_partial(self, mods):
        if self.hist_plot_data is None:
            return False
        for mod in mods:
            if mod["action"] != "setitem":
                return False
            if mod["path"] == [self.args.xs, 1]:
                if mod["key"] == self.selected_index:
                    return False
            elif mod["path"][:2] == [self.args.histograms_counts, 1]:
                if len(mod["path"]) > 2:
                    index = mod["path"][2]
                else:
                    index = mod["key"]
                if index == self.selected_index:
                    return False
            else:
                return False
        return True

    def data_changed(self, data, mods):
        try:
            xs = data[self.args.xs][1]
            histogram_bins = data[self.args.histogram_bins][1]
            histograms_counts = data[self.args.histograms_counts][1]
        except KeyError:
            return
        if self._can_use_partial(mods):
            self._set_partial_data(xs, histograms_counts)
        else:
            self._set_full_data(xs, histogram_bins, histograms_counts)


def main():
    applet = SimpleApplet(XYHistPlot)
    applet.add_dataset("xs", "1D array of point abscissas")
    applet.add_dataset("histogram_bins",
                       "1D array of histogram bin boundaries")
    applet.add_dataset("histograms_counts",
                       "2D array of histogram counts, for each point")
    applet.run()

if __name__ == "__main__":
    main()
