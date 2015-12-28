#!/usr/bin/env python3.5

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg

import numpy as np

class XYHistPlot:
    def __init__(self):
        self.graphics_window = pg.GraphicsWindow(title="XY/Histogram")
        self.graphics_window.resize(1000,600)
        self.graphics_window.setWindowTitle("XY/Histogram")

        self.xy_plot = self.graphics_window.addPlot()
        self.xy_plot_data = None
        self.arrow = None

        self.hist_plot = self.graphics_window.addPlot()
        self.hist_plot_data = None

    def set_data(self, xs, histograms_bins, histograms_counts):
        ys = np.empty_like(xs)
        ys.fill(np.nan)
        for n, (bins, counts) in enumerate(zip(histograms_bins,
                                               histograms_counts)):
            bin_centers = np.empty(len(bins)-1)
            for i in range(len(bin_centers)):
                bin_centers[i] = (bins[i] + bins[i+1])/2
            ys[n] = sum(bin_centers*counts)/sum(bin_centers)

        self.xy_plot_data = self.xy_plot.plot(x=xs, y=ys,
                                              pen=None,
                                              symbol="x", symbolSize=20)
        self.xy_plot_data.sigPointsClicked.connect(self.point_clicked)
        for point, bins, counts in zip(self.xy_plot_data.scatter.points(),
                                       histograms_bins, histograms_counts):
            point.histogram_bins = bins
            point.histogram_counts = counts

        self.hist_plot_data = self.hist_plot.plot(
                            stepMode=True, fillLevel=0,
                            brush=(0, 0, 255, 150))

    def point_clicked(self, data_item, spot_items):
        spot_item = spot_items[0]
        position = spot_item.pos()
        if self.arrow is None:
            self.arrow = pg.ArrowItem(angle=-120, tipAngle=30, baseAngle=20,
                                      headLen=40, tailLen=40, tailWidth=8,
                                      pen=None, brush="y")
            self.arrow.setPos(position)
            # NB: temporary glitch if addItem is done before setPos
            self.xy_plot.addItem(self.arrow)
        else:
            self.arrow.setPos(position)
        self.hist_plot_data.setData(x=spot_item.histogram_bins,
                                    y=spot_item.histogram_counts)
        

def main():
    app = QtGui.QApplication([])
    plot = XYHistPlot()
    plot.set_data(np.array([1, 2, 3, 4, 1]),
                  np.array([[1, 2, 3], [1, 2, 3], [1, 2, 3], [40, 70, 100], [4, 7, 10, 20]]),
                  np.array([[1, 1], [2, 3], [10, 20], [3, 1], [100, 67, 102]]))
    app.exec_()

if __name__ == '__main__':
    main()
