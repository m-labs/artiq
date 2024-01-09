from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt

from artiq.gui.models import DictSyncTreeSepModel, LocalModelManager

import numpy as np
import itertools
import bisect
import pyqtgraph as pg
import logging
import math

logger = logging.getLogger(__name__)

DISPLAY_LOW = 0
DISPLAY_HIGH = 1
DISPLAY_MID = 0.5


class Model(DictSyncTreeSepModel):
    def __init__(self, init):
        DictSyncTreeSepModel.__init__(self, "/", ["Channels"], init)


class _AddChannelDialog(QtWidgets.QDialog):
    accepted = QtCore.pyqtSignal(list)

    def __init__(self, parent, channels_mgr):
        QtWidgets.QDialog.__init__(self, parent=parent)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.setWindowTitle("Add channels")

        grid = QtWidgets.QGridLayout()
        self.setLayout(grid)

        self._channels_widget = QtWidgets.QTreeView()
        self._channels_widget.setHeaderHidden(True)
        self._channels_widget.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectItems)
        self._channels_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        grid.addWidget(self._channels_widget, 0, 0, 1, 2)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DialogCancelButton))
        grid.addWidget(cancel_btn, 1, 0)
        confirm_btn = QtWidgets.QPushButton("Confirm")
        confirm_btn.clicked.connect(self.add_channels)
        confirm_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DialogApplyButton))
        grid.addWidget(confirm_btn, 1, 1)

        self._model = Model(dict())
        channels_mgr.add_setmodel_callback(self.set_model)

    def set_model(self, model):
        self._model = model
        self._channels_widget.setModel(model)

    def add_channels(self):
        selection = self._channels_widget.selectedIndexes()
        channels = []
        for select in selection:
            key = self._model.index_to_key(select)
            if key is not None:
                width = self._model[key].ref
                channels.append((key, width))
        self.accepted.emit(channels)
        self.close()


class BackgroundItem(pg.GraphicsWidgetAnchor, pg.GraphicsWidget):
    def __init__(self, parent, rect):
        pg.GraphicsWidget.__init__(self, parent)
        pg.GraphicsWidgetAnchor.__init__(self)
        self.item = QtWidgets.QGraphicsRectItem(rect, self)
        brush = QtGui.QBrush(QtGui.QColor(10, 10, 10, 140))
        self.item.setBrush(brush)


class Waveform(pg.PlotWidget):
    MIN_HEIGHT = 50
    MAX_HEIGHT = 200
    PREF_HEIGHT = 75

    cursorMoved = QtCore.pyqtSignal(float)

    def __init__(self, channel, state, parent=None):
        pg.PlotWidget.__init__(self,
                               parent=parent,
                               x=None,
                               y=None,
                               pen="r",
                               stepMode="right",
                               connect="finite")

        self.setMinimumHeight(Waveform.MIN_HEIGHT)
        self.setMaximumHeight(Waveform.MAX_HEIGHT)
        self.setMenuEnabled(False)
        self.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)

        self.channel = channel
        self.name = channel[0]
        self.width = channel[1][0]

        self.state = state
        self.x_data = []
        self.y_data = []

        self.plot_item = self.getPlotItem()
        self.plot_item.hideButtons()
        self.plot_item.getAxis("bottom").setStyle(showValues=False, tickLength=0)
        self.plot_item.hideAxis("top")
        self.plot_item.getAxis("left").setStyle(showValues=False, tickLength=0)
        self.plot_item.setRange(yRange=(DISPLAY_LOW, DISPLAY_HIGH), padding=0.1)
        self.plot_item.showGrid(x=True, y=True)

        self.plot_data_item = self.plot_item.listDataItems()[0]
        self.plot_data_item.setClipToView(True)

        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=False)
        self.view_box.disableAutoRange(axis=pg.ViewBox.YAxis)
        self.view_box.setLimits(xMin=0, minXRange=20)

        self.cursor = pg.InfiniteLine()
        self.cursor_y = 0
        self.addItem(self.cursor)

        self.cursor_label = pg.LabelItem('', parent=self.plot_item)
        self.cursor_label.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, 20))
        self.cursor_label.setAttr('justify', 'left')
        self.cursor_label.setZValue(10)

        self.title_label = pg.LabelItem(self.name, parent=self.plot_item)
        self.title_label.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, 0))
        self.title_label.setAttr('justify', 'left')
        self.title_label.setZValue(10)

        rect = self.title_label.boundingRect()
        rect.setHeight(rect.height() * 2)
        self.label_bg = BackgroundItem(parent=self.plot_item, rect=rect)
        self.label_bg.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, 0))

    def update_x_max(self):
        self.view_box.setLimits(xMax=self.state["stopped_x"])

    def set_cursor_visible(self, visible):
        if visible:
            self.addItem(self.cursor)
        else:
            self.removeItem(self.cursor)

    def on_cursor_move(self, x):
        self.cursor.setValue(x)
        if len(self.x_data) < 1:
            return
        ind = bisect.bisect_left(self.x_data, x) - 1
        dr = self.plot_data_item.dataRect()
        if dr is None:
            self.cursor_y = None
        elif dr.left() <= x \
                and 0 <= ind < len(self.y_data):
            self.cursor_y = self.y_data[ind]
        elif x >= dr.right():
            self.cursor_y = self.y_data[-1]
        else:
            self.cursor_y = None
        self.format_cursor_label()

    def extract_data_from_state(self):
        raise NotImplementedError

    def display(self):
        raise NotImplementedError

    def format_cursor_label(self):
        raise NotImplementedError

    # override
    def mouseMoveEvent(self, e):
        if e.buttons() == QtCore.Qt.LeftButton \
           and e.modifiers() == QtCore.Qt.ShiftModifier:
            drag = QtGui.QDrag(self)
            mime = QtCore.QMimeData()
            drag.setMimeData(mime)
            pixmapi = QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_FileIcon)
            drag.setPixmap(pixmapi.pixmap(32))
            drag.exec_(QtCore.Qt.MoveAction)
        else:
            super().mouseMoveEvent(e)

    # override
    def mouseDoubleClickEvent(self, e):
        pos = self.view_box.mapSceneToView(e.pos())
        self.cursorMoved.emit(pos.x())

    # override
    def wheelEvent(self, e):
        if e.modifiers() & QtCore.Qt.ControlModifier:
            super().wheelEvent(e)


class LogWaveform(Waveform):
    def __init__(self, channel, state, parent=None):
        Waveform.__init__(self, channel, state, parent)

    def extract_data_from_state(self):
        try:
            self.x_data, self.y_data = zip(*self.state['logs'][self.name])
        except:
            logger.debug('Error caught when loading waveform: {}'.format(self.name), exc_info=True)

    def display(self):
        try:
            self.plot_data_item.setData(
                x=self.x_data, y=np.ones(len(self.x_data)))
            self.plot_data_item.opts.update(
                {"connect": np.zeros(2), "symbol": "x"})
            old_msg = ""
            old_x = 0
            for x, msg in zip(self.x_data, self.y_data):
                if x == old_x:
                    old_msg += "\n" + msg
                else:
                    lbl = pg.TextItem(old_msg)
                    self.addItem(lbl)
                    lbl.setPos(old_x, DISPLAY_HIGH)
                    old_msg = msg
                    old_x = x
            lbl = pg.TextItem(old_msg)
            self.addItem(lbl)
            lbl.setPos(old_x, DISPLAY_HIGH)
        except:
            logger.debug('Error caught when displaying waveform: {}'.format(self.name), exc_info=True)
            self.plot_data_item.setData(x=[], y=[])

    def format_cursor_label(self):
        self.cursor_label.setText("")


class BitWaveform(Waveform):
    def __init__(self, channel, state, parent=None):
        Waveform.__init__(self, channel, state, parent)
        self._arrows = []

    def extract_data_from_state(self):
        try:
            self.x_data, self.y_data = zip(*self.state['data'][self.name])
        except:
            logger.debug('Error caught when loading waveform data: {}'.format(self.name), exc_info=True)

    def display(self):
        try:
            display_y = []
            display_x = []
            previous_y = None
            for x, y in zip(self.x_data, self.y_data):
                state_unchanged = previous_y == y
                if y is None:
                    dis_y = DISPLAY_MID
                elif y == 1:
                    dis_y = DISPLAY_HIGH
                else:
                    dis_y = DISPLAY_LOW
                if state_unchanged:
                    arw = pg.ArrowItem(pxMode=True, angle=90)
                    self.addItem(arw)
                    self._arrows.append(arw)
                    arw.setPos(x, dis_y)
                display_y.append(dis_y)
                display_x.append(x)
                previous_y = y
            self.plot_data_item.setData(x=display_x, y=display_y)
        except:
            logger.debug('Error caught when displaying waveform: {}'.format(self.name), exc_info=True)
            for arw in self._arrows:
                self.removeItem(arw)
            self.plot_data_item.setData(x=[], y=[])

    def format_cursor_label(self):
        if self.cursor_y is None:
            lbl = "x"
        else:
            lbl = str(self.cursor_y)
        self.cursor_label.setText(lbl)


class BitVectorWaveform(Waveform):
    def __init__(self, channel, state, parent=None):
        Waveform.__init__(self, channel, state, parent)
        self._labels = []
        hx = math.ceil(self.width / 4)
        self._format_string = "{:0=" + str(hx) + "X}"
        self.view_box.sigTransformChanged.connect(self._update_labels)

    def _update_labels(self):
        for label in self._labels:
            self.removeItem(label)
        xmin, xmax = self.view_box.viewRange()[0]
        left_label_i = bisect.bisect_left(self.x_data, xmin)
        right_label_i = bisect.bisect_right(self.x_data, xmax) + 1
        for i, j in itertools.pairwise(range(left_label_i, right_label_i)):
            x1 = self.x_data[i]
            x2 = self.x_data[j] if j < len(self.x_data) else self.state["stopped_x"]
            lbl = self._labels[i]
            bounds = lbl.boundingRect()
            bounds_view = self.view_box.mapSceneToView(bounds)
            if bounds_view.boundingRect().width() < x2 - x1:
                self.addItem(lbl)

    def extract_data_from_state(self):
        try:
            self.x_data, self.y_data = zip(*self.state['data'][self.name])
        except:
            logger.debug('Error caught when loading waveform data: {}'.format(self.name), exc_info=True)

    def display(self):
        try:
            display_x, display_y = [], []
            for x, y in zip(self.x_data, self.y_data):
                display_x.append(x)
                display_y.append(DISPLAY_LOW)
                if y is None:
                    display_x.append(x)
                    display_y.append(DISPLAY_MID)
                elif y != 0:
                    display_x.append(x)
                    display_y.append(DISPLAY_HIGH)
                lbl = pg.TextItem(
                    self._format_string.format(y), anchor=(0, DISPLAY_MID))
                lbl.setPos(x, DISPLAY_MID)
                lbl.setTextWidth(100)
                self._labels.append(lbl)
            self.plot_data_item.setData(x=display_x, y=display_y)
        except:
            logger.debug('Error caught when displaying waveform: {}'.format(self.name), exc_info=True)
            for lbl in self._labels:
                self.plot_item.removeItem(lbl)
            self.plot_data_item.setData(x=[], y=[])

    def format_cursor_label(self):
        if self.cursor_y is None:
            lbl = "X"
        else:
            lbl = self._format_string.format(self.cursor_y)
        self.cursor_label.setText(lbl)


class AnalogWaveform(Waveform):
    def __init__(self, channel, state, parent=None):
        Waveform.__init__(self, channel, state, parent)
        self.plot_data_item.setDownsampling(ds=10, method="peak", auto=True)

    def extract_data_from_state(self):
        try:
            self.x_data, self.y_data = zip(*self.state['data'][self.name])
        except:
            logger.debug('Error caught when loading waveform data: {}'.format(self.name), exc_info=True)

    def display(self):
        try:
            self.plot_data_item.setData(x=self.x_data, y=self.y_data)
            mx = max(self.y_data)
            mn = min(self.y_data)
            self.plot_item.setRange(yRange=(mn, mx), padding=0.1)
        except:
            logger.debug('Error caught when displaying waveform: {}'.format(self.name), exc_info=True)
            self.plot_data_item.setData(x=[0], y=[0])

    def format_cursor_label(self):
        if self.cursor_y is None:
            lbl = "nan"
        else:
            lbl = str(self.cursor_y)
        self.cursor_label.setText(lbl)
