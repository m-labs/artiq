#!/usr/bin/env python3.5

import numpy as np
import pyqtgraph

from artiq.applets.simple import SimpleApplet


class XYHistPlot(pyqtgraph.GraphicsWindow):
    def __init__(self, args):
        pyqtgraph.GraphicsWindow.__init__(self, title="XY/Histogram")
        self.resize(1000,600)
        self.setWindowTitle("XY/Histogram")

        self.xy_plot = self.addPlot()
        self.xy_plot_data = None
        self.arrow = None

        self.hist_plot = self.addPlot()
        self.hist_plot_data = None

        self.args = args

    def _set_full_data(self, xs, histogram_bins, histograms_counts):
        self.xy_plot.clear()
        self.hist_plot.clear()
        self.xy_plot_data = None
        self.hist_plot_data = None
        self.arrow = None

        self.histogram_bins = histogram_bins
        bin_centers = np.empty(len(histogram_bins)-1)
        for i in range(len(bin_centers)):
            bin_centers[i] = (histogram_bins[i] + histogram_bins[i+1])/2

        ys = np.empty_like(xs)
        for n, counts in enumerate(histograms_counts):
            ys[n] = sum(bin_centers*counts)/sum(counts)

        self.xy_plot_data = self.xy_plot.plot(x=xs, y=ys,
                                              pen=None,
                                              symbol="x", symbolSize=20)
        self.xy_plot_data.sigPointsClicked.connect(self._point_clicked)
        for point, counts in zip(self.xy_plot_data.scatter.points(),
                                 histograms_counts):
            point.histogram_counts = counts

        self.hist_plot_data = self.hist_plot.plot(
            stepMode=True, fillLevel=0,
            brush=(0, 0, 255, 150))

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
        self.hist_plot_data.setData(x=self.histogram_bins,
                                    y=spot_item.histogram_counts)

    def data_changed(self, data, mods):
        xs = data[self.args.xs][1]
        histogram_bins = data[self.args.histogram_bins][1]
        histograms_counts = data[self.args.histograms_counts][1]
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
