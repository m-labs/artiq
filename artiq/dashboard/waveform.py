import os
import asyncio
import logging
import bisect
import itertools
import math

from PyQt6 import QtCore, QtWidgets, QtGui

import pyqtgraph as pg
import numpy as np

from sipyco.pc_rpc import AsyncioClient
from sipyco import pyon

from artiq.tools import exc_to_warning, short_format
from artiq.coredevice import comm_analyzer
from artiq.coredevice.comm_analyzer import WaveformType
from artiq.gui.tools import LayoutWidget, get_open_file_name, get_save_file_name
from artiq.gui.models import DictSyncTreeSepModel
from artiq.gui.dndwidgets import VDragScrollArea, VDragDropSplitter


logger = logging.getLogger(__name__)

WAVEFORM_MIN_HEIGHT = 50
WAVEFORM_MAX_HEIGHT = 200


class ProxyClient():
    def __init__(self, receive_cb, timeout=5, timer=5, timer_backoff=1.1, ssl_config=None):
        self.receive_cb = receive_cb
        self.receiver = None
        self.addr = None
        self.port_proxy = None
        self.port = None
        self._reconnect_event = asyncio.Event()
        self.timeout = timeout
        self.timer = timer
        self.timer_cur = timer
        self.timer_backoff = timer_backoff
        self.ssl_config = ssl_config
        self._reconnect_task = asyncio.ensure_future(self._reconnect())

    def update_address(self, addr, port, port_proxy):
        self.addr = addr
        self.port = port
        self.port_proxy = port_proxy
        self._reconnect_event.set()

    async def trigger_proxy_task(self):
        remote = AsyncioClient()
        try:
            try:
                if self.addr is None:
                    logger.error("missing core_analyzer host in device db")
                    return
                await remote.connect_rpc(self.addr, self.port, "coreanalyzer_proxy_control", self.ssl_config)
            except:
                logger.error("error connecting to analyzer proxy control", exc_info=True)
                return
            await remote.trigger()
        except:
            logger.error("analyzer proxy reported failure", exc_info=True)
        finally:
            await remote.close_rpc()

    async def _reconnect(self):
        while True:
            await self._reconnect_event.wait()
            self._reconnect_event.clear()
            if self.receiver is not None:
                await self.receiver.close()
                self.receiver = None
            new_receiver = comm_analyzer.AnalyzerProxyReceiver(
                self.receive_cb, self.disconnect_cb)
            try:
                if self.addr is not None:
                    await asyncio.wait_for(new_receiver.connect(self.addr, self.port_proxy, self.ssl_config),
                                           self.timeout)
                    logger.info("ARTIQ dashboard connected to analyzer proxy (%s)", self.addr)
                    self.timer_cur = self.timer
                    self.receiver = new_receiver
                continue
            except Exception:
                logger.error("error connecting to analyzer proxy", exc_info=True)
            try:
                await asyncio.wait_for(self._reconnect_event.wait(), self.timer_cur)
            except asyncio.TimeoutError:
                self.timer_cur *= self.timer_backoff
                self._reconnect_event.set()
            else:
                self.timer_cur = self.timer

    async def close(self):
        self._reconnect_task.cancel()
        try:
            await asyncio.wait_for(self._reconnect_task, None)
        except asyncio.CancelledError:
            pass
        if self.receiver is not None:
            await self.receiver.close()

    def disconnect_cb(self):
        logger.error("lost connection to analyzer proxy")
        self._reconnect_event.set()


class _BackgroundItem(pg.GraphicsWidgetAnchor, pg.GraphicsWidget):
    def __init__(self, parent, rect):
        pg.GraphicsWidget.__init__(self, parent)
        pg.GraphicsWidgetAnchor.__init__(self)
        self.item = QtWidgets.QGraphicsRectItem(rect, self)
        brush = QtGui.QBrush(QtGui.QColor(10, 10, 10, 140))
        self.item.setBrush(brush)


class _BaseWaveform(pg.PlotWidget):
    cursorMove = QtCore.pyqtSignal(float)

    def __init__(self, name, width, precision, unit,
                 parent=None, pen="r", stepMode="right", connect="finite"):
        pg.PlotWidget.__init__(self,
                               parent=parent,
                               x=None,
                               y=None,
                               pen=pen,
                               stepMode=stepMode,
                               connect=connect)

        self.setMinimumHeight(WAVEFORM_MIN_HEIGHT)
        self.setMaximumHeight(WAVEFORM_MAX_HEIGHT)
        self.setMenuEnabled(False)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)

        self.name = name
        self.width = width
        self.precision = precision
        self.unit = unit

        self.x_data = []
        self.y_data = []

        self.plot_item = self.getPlotItem()
        self.plot_item.hideButtons()
        self.plot_item.hideAxis("top")
        self.plot_item.getAxis("bottom").setStyle(showValues=False, tickLength=0)
        self.plot_item.getAxis("left").setStyle(showValues=False, tickLength=0)
        self.plot_item.setRange(yRange=(0, 1), padding=0.1)
        self.plot_item.showGrid(x=True, y=True)

        self.plot_data_item = self.plot_item.listDataItems()[0]
        self.plot_data_item.setClipToView(True)

        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=False)
        self.view_box.disableAutoRange(axis=pg.ViewBox.YAxis)
        self.view_box.setLimits(xMin=0, minXRange=20)

        self.title_label = pg.LabelItem(self.name, parent=self.plot_item)
        self.title_label.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, 0))
        self.title_label.setAttr('justify', 'left')
        self.title_label.setZValue(10)

        rect = self.title_label.boundingRect()
        rect.setHeight(rect.height() * 2)
        rect.setWidth(225)
        self.label_bg = _BackgroundItem(parent=self.plot_item, rect=rect)
        self.label_bg.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, 0))

        self.cursor = pg.InfiniteLine()
        self.cursor_y = None
        self.addItem(self.cursor)

        self.cursor_label = pg.LabelItem('', parent=self.plot_item)
        self.cursor_label.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(0, 20))
        self.cursor_label.setAttr('justify', 'left')
        self.cursor_label.setZValue(10)

    def setStoppedX(self, stopped_x):
        self.stopped_x = stopped_x
        self.view_box.setLimits(xMax=stopped_x)

    def setData(self, data):
        if len(data) == 0:
            self.x_data, self.y_data = [], []
        else:
            self.x_data, self.y_data = zip(*data)

    def onDataChange(self, data):
        raise NotImplementedError

    def onCursorMove(self, x):
        self.cursor.setValue(x)
        if len(self.x_data) < 1:
            return
        ind = bisect.bisect_left(self.x_data, x) - 1
        dr = self.plot_data_item.dataRect()
        self.cursor_y = None
        if dr is not None and 0 <= ind < len(self.y_data):
            self.cursor_y = self.y_data[ind]

    def mouseMoveEvent(self, e):
        if e.buttons() == QtCore.Qt.MouseButton.LeftButton \
           and e.modifiers() == QtCore.Qt.KeyboardModifier.ShiftModifier:
            drag = QtGui.QDrag(self)
            mime = QtCore.QMimeData()
            drag.setMimeData(mime)
            pixmapi = QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
            drag.setPixmap(pixmapi.pixmap(32))
            drag.exec(QtCore.Qt.DropAction.MoveAction)
        else:
            super().mouseMoveEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            super().wheelEvent(e)
        else:
            e.ignore()


    def mouseDoubleClickEvent(self, e):
        pos = self.view_box.mapSceneToView(e.position())
        self.cursorMove.emit(pos.x())


class BitWaveform(_BaseWaveform):
    def __init__(self, name, width, precision, unit, parent=None):
        _BaseWaveform.__init__(self, name, width, precision, unit, parent)
        self.plot_item.showGrid(x=True, y=False)
        self._arrows = []

    def onDataChange(self, data):
        try:
            self.setData(data)
            for arw in self._arrows:
                self.removeItem(arw)
            self._arrows = []
            l = len(data)
            display_y = np.empty(l)
            display_x = np.empty(l)
            display_map = {
                "X": 0.5,
                "1": 1,
                "0": 0
            }
            previous_y = None
            for i, coord in enumerate(data):
                x, y = coord
                dis_y = display_map[y]
                if previous_y == y:
                    arw = pg.ArrowItem(pxMode=True, angle=90)
                    self.addItem(arw)
                    self._arrows.append(arw)
                    arw.setPos(x, dis_y)
                display_y[i] = dis_y
                display_x[i] = x
                previous_y = y
            self.plot_data_item.setData(x=display_x, y=display_y)
        except:
            logger.error("Error when displaying waveform: %s", self.name, exc_info=True)
            for arw in self._arrows:
                self.removeItem(arw)
            self.plot_data_item.setData(x=[], y=[])

    def onCursorMove(self, x):
        _BaseWaveform.onCursorMove(self, x)
        if self.cursor_y is not None:
            self.cursor_label.setText(self.cursor_y)
        else:
            self.cursor_label.setText("")


class AnalogWaveform(_BaseWaveform):
    def __init__(self, name, width, precision, unit, parent=None):
        _BaseWaveform.__init__(self, name, width, precision, unit, parent)

    def onDataChange(self, data):
        try:
            self.setData(data)
            self.plot_data_item.setData(x=self.x_data, y=self.y_data)
            if len(data) > 0:
                max_y = max(self.y_data)
                min_y = min(self.y_data)
                self.plot_item.setRange(yRange=(min_y, max_y), padding=0.1)
        except:
            logger.error("Error when displaying waveform: %s", self.name, exc_info=True)
            self.plot_data_item.setData(x=[], y=[])

    def onCursorMove(self, x):
        _BaseWaveform.onCursorMove(self, x)
        if self.cursor_y is not None:
            t = short_format(self.cursor_y, {"precision": self.precision, "unit": self.unit})
        else:
            t = ""
        self.cursor_label.setText(t)


class BitVectorWaveform(_BaseWaveform):
    def __init__(self, name, width, precision, unit, parent=None):
        _BaseWaveform.__init__(self, name, width, precision, parent)
        self._labels = []
        self._format_string = "{:0=" + str(math.ceil(width / 4)) + "X}"
        self.view_box.sigTransformChanged.connect(self._update_labels)
        self.plot_item.showGrid(x=True, y=False)

    def _update_labels(self):
        for label in self._labels:
            self.removeItem(label)
        xmin, xmax = self.view_box.viewRange()[0]
        left_label_i = bisect.bisect_left(self.x_data, xmin)
        right_label_i = bisect.bisect_right(self.x_data, xmax) + 1
        for i, j in itertools.pairwise(range(left_label_i, right_label_i)):
            x1 = self.x_data[i]
            x2 = self.x_data[j] if j < len(self.x_data) else self.stopped_x
            lbl = self._labels[i]
            bounds = lbl.boundingRect()
            bounds_view = self.view_box.mapSceneToView(bounds)
            if bounds_view.boundingRect().width() < x2 - x1:
                self.addItem(lbl)

    def onDataChange(self, data):
        try:
            self.setData(data)
            for lbl in self._labels:
                self.plot_item.removeItem(lbl)
            self._labels = []
            l = len(data)
            display_x = np.empty(l * 2)
            display_y = np.empty(l * 2)
            for i, coord in enumerate(data):
                x, y = coord
                display_x[i * 2] = x
                display_x[i * 2 + 1] = x
                display_y[i * 2] = 0
                display_y[i * 2 + 1] = int(int(y) != 0)
                lbl = pg.TextItem(
                    self._format_string.format(int(y, 2)), anchor=(0, 0.5))
                lbl.setPos(x, 0.5)
                lbl.setTextWidth(100)
                self._labels.append(lbl)
            self.plot_data_item.setData(x=display_x, y=display_y)
        except:
            logger.error("Error when displaying waveform: %s", self.name, exc_info=True)
            for lbl in self._labels:
                self.plot_item.removeItem(lbl)
            self.plot_data_item.setData(x=[], y=[])

    def onCursorMove(self, x):
        _BaseWaveform.onCursorMove(self, x)
        if self.cursor_y is not None:
            t = self._format_string.format(int(self.cursor_y, 2))
        else:
            t = ""
        self.cursor_label.setText(t)


class LogWaveform(_BaseWaveform):
    def __init__(self, name, width, precision, unit, parent=None):
        _BaseWaveform.__init__(self, name, width, precision, parent)
        self.plot_data_item.opts['pen'] = None
        self.plot_data_item.opts['symbol'] = 'x'
        self._labels = []
        self.plot_item.showGrid(x=True, y=False)

    def onDataChange(self, data):
        try:
            self.setData(data)
            for lbl in self._labels:
                self.plot_item.removeItem(lbl)
            self._labels = []
            self.plot_data_item.setData(
                x=self.x_data, y=np.ones(len(self.x_data)))
            if len(data) == 0:
                return
            old_x = data[0][0]
            old_msg = data[0][1]
            for x, msg in data[1:]:
                if x == old_x:
                    old_msg += "\n" + msg
                else:
                    lbl = pg.TextItem(old_msg)
                    self.addItem(lbl)
                    self._labels.append(lbl)
                    lbl.setPos(old_x, 1)
                    old_msg = msg
                    old_x = x
            lbl = pg.TextItem(old_msg)
            self.addItem(lbl)
            self._labels.append(lbl)
            lbl.setPos(old_x, 1)
        except:
            logger.error("Error when displaying waveform: %s", self.name, exc_info=True)
            for lbl in self._labels:
                self.plot_item.removeItem(lbl)
            self.plot_data_item.setData(x=[], y=[])


# pg.GraphicsView ignores dragEnterEvent but not dragLeaveEvent
# https://github.com/pyqtgraph/pyqtgraph/blob/1e98704eac6b85de9c35371079f561042e88ad68/pyqtgraph/widgets/GraphicsView.py#L388
class _RefAxis(pg.PlotWidget):
    def dragLeaveEvent(self, ev):
        ev.ignore()


class _WaveformView(QtWidgets.QWidget):
    cursorMove = QtCore.pyqtSignal(float)

    def __init__(self, parent):
        QtWidgets.QWidget.__init__(self, parent=parent)

        self._stopped_x = None
        self._timescale = 1
        self._cursor_x = 0

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self._ref_axis = _RefAxis()
        self._ref_axis.hideAxis("bottom")
        self._ref_axis.hideAxis("left")
        self._ref_axis.hideButtons()
        self._ref_axis.setFixedHeight(45)
        self._ref_axis.setMenuEnabled(False)
        self._top = pg.AxisItem("top")
        self._top.setScale(1e-12)
        self._top.setLabel(units="s")
        self._ref_axis.setAxisItems({"top": self._top})
        layout.addWidget(self._ref_axis)

        self._ref_vb = self._ref_axis.getPlotItem().getViewBox()
        self._ref_vb.setFixedHeight(0)
        self._ref_vb.setMouseEnabled(x=True, y=False)
        self._ref_vb.setLimits(xMin=0)

        scroll_area = VDragScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setContentsMargins(0, 0, 0, 0)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll_area)

        self._splitter = VDragDropSplitter(parent=scroll_area)
        self._splitter.setHandleWidth(1)
        scroll_area.setWidget(self._splitter)

        self.cursorMove.connect(self.onCursorMove)

        self.confirm_delete_dialog = QtWidgets.QMessageBox(self)
        self.confirm_delete_dialog.setIcon(
            QtWidgets.QMessageBox.Icon.Warning
        )
        self.confirm_delete_dialog.setText("Delete all waveforms?")
        self.confirm_delete_dialog.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Ok | 
            QtWidgets.QMessageBox.StandardButton.Cancel
        )
        self.confirm_delete_dialog.setDefaultButton(
            QtWidgets.QMessageBox.StandardButton.Ok
        )

    def setModel(self, model):
        self._model = model
        self._model.dataChanged.connect(self.onDataChange)
        self._model.rowsInserted.connect(self.onInsert)
        self._model.rowsRemoved.connect(self.onRemove)
        self._model.rowsMoved.connect(self.onMove)
        self._splitter.dropped.connect(self._model.move)
        self.confirm_delete_dialog.accepted.connect(self._model.clear)

    def setTimescale(self, timescale):
        self._timescale = timescale
        self._top.setScale(1e-12 * timescale)

    def setStoppedX(self, stopped_x):
        self._stopped_x = stopped_x
        self._ref_vb.setLimits(xMax=stopped_x)
        self._ref_vb.setRange(xRange=(0, stopped_x))
        for i in range(self._model.rowCount()):
            self._splitter.widget(i).setStoppedX(stopped_x)

    def resetZoom(self):
        if self._stopped_x is not None:
            self._ref_vb.setRange(xRange=(0, self._stopped_x))

    def onDataChange(self, top, bottom, roles):
        self.cursorMove.emit(0)
        first = top.row()
        last = bottom.row()
        data_row = self._model.headers.index("data")
        for i in range(first, last + 1):
            data = self._model.data(self._model.index(i, data_row))
            self._splitter.widget(i).onDataChange(data)

    def onInsert(self, parent, first, last):
        for i in range(first, last + 1):
            w = self._create_waveform(i)
            self._splitter.insertWidget(i, w)
        self._resize()

    def onRemove(self, parent, first, last):
        for i in reversed(range(first, last + 1)):
            w = self._splitter.widget(i)
            w.deleteLater()
        self._splitter.refresh()
        self._resize()

    def onMove(self, src_parent, src_start, src_end, dest_parent, dest_row):
        w = self._splitter.widget(src_start)
        self._splitter.insertWidget(dest_row, w)

    def onCursorMove(self, x):
        self._cursor_x = x
        for i in range(self._model.rowCount()):
            self._splitter.widget(i).onCursorMove(x)

    def _create_waveform(self, row):
        name, ty, width, precision, unit = (
            self._model.data(self._model.index(row, i)) for i in range(5))
        waveform_cls = {
            WaveformType.BIT: BitWaveform,
            WaveformType.VECTOR: BitVectorWaveform,
            WaveformType.ANALOG: AnalogWaveform,
            WaveformType.LOG: LogWaveform
        }[ty]
        w = waveform_cls(name, width, precision, unit, parent=self._splitter)
        w.setXLink(self._ref_vb)
        w.setStoppedX(self._stopped_x)
        w.cursorMove.connect(self.cursorMove)
        w.onCursorMove(self._cursor_x)
        action = QtGui.QAction("Delete waveform", w)
        action.triggered.connect(lambda: self._delete_waveform(w))
        w.addAction(action)
        action = QtGui.QAction("Delete all waveforms", w)
        action.triggered.connect(self.confirm_delete_dialog.open)
        w.addAction(action)
        return w

    def _delete_waveform(self, waveform):
        row = self._splitter.indexOf(waveform)
        self._model.pop(row)

    def _resize(self):
        self._splitter.setFixedHeight(
            int((WAVEFORM_MIN_HEIGHT + WAVEFORM_MAX_HEIGHT) * self._model.rowCount() / 2))


class _WaveformModel(QtCore.QAbstractTableModel):
    def __init__(self):
        self.backing_struct = []
        self.headers = ["name", "type", "width", "precision", "unit", "data"]
        QtCore.QAbstractTableModel.__init__(self)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.backing_struct)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.headers)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            return self.backing_struct[index.row()][index.column()]
        return None

    def extend(self, data):
        length = len(self.backing_struct)
        len_data = len(data)
        self.beginInsertRows(QtCore.QModelIndex(), length, length + len_data - 1)
        self.backing_struct.extend(data)
        self.endInsertRows()

    def pop(self, row):
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.backing_struct.pop(row)
        self.endRemoveRows()

    def move(self, src, dest):
        if src == dest:
            return
        if src < dest:
            dest, src = src, dest
        self.beginMoveRows(QtCore.QModelIndex(), src, src, QtCore.QModelIndex(), dest)
        self.backing_struct.insert(dest, self.backing_struct.pop(src))
        self.endMoveRows()

    def clear(self):
        self.beginRemoveRows(QtCore.QModelIndex(), 0, len(self.backing_struct) - 1)
        self.backing_struct.clear()
        self.endRemoveRows()

    def export_list(self):
        return [[row[0], row[1].value, *row[2:5]] for row in self.backing_struct]

    def import_list(self, channel_list):
        self.clear()
        data = [[row[0], WaveformType(row[1]), *row[2:5], []] for row in channel_list]
        self.extend(data)

    def update_data(self, waveform_data, top, bottom):
        name_col = self.headers.index("name")
        data_col = self.headers.index("data")
        for i in range(top, bottom):
            name = self.data(self.index(i, name_col))
            self.backing_struct[i][data_col] = waveform_data.get(name, [])
            self.dataChanged.emit(self.index(i, data_col),
                                  self.index(i, data_col))

    def update_all(self, waveform_data):
        self.update_data(waveform_data, 0, self.rowCount())


class _CursorTimeControl(QtWidgets.QLineEdit):
    submit = QtCore.pyqtSignal(float)

    def __init__(self, parent):
        QtWidgets.QLineEdit.__init__(self, parent=parent)
        self._text = ""
        self._value = 0
        self._timescale = 1
        self.setDisplayValue(0)
        self.textChanged.connect(self._onTextChange)
        self.returnPressed.connect(self._onReturnPress)

    def setTimescale(self, timescale):
        self._timescale = timescale

    def _onTextChange(self, text):
        self._text = text

    def setDisplayValue(self, value):
        self._value = value
        self._text = pg.siFormat(value * 1e-12 * self._timescale,
                                 suffix="s",
                                 allowUnicode=False,
                                 precision=15)
        self.setText(self._text)

    def _setValueFromText(self, text):
        try:
            self._value = pg.siEval(text) * (1e12 / self._timescale)
        except:
            logger.error("Error when parsing cursor time input", exc_info=True)

    def _onReturnPress(self):
        self._setValueFromText(self._text)
        self.setDisplayValue(self._value)
        self.submit.emit(self._value)
        self.clearFocus()


class Model(DictSyncTreeSepModel):
    def __init__(self, init):
        DictSyncTreeSepModel.__init__(self, "/", ["Channels"], init)

    def clear(self):
        for k in self.backing_store:
            self._del_item(self, k.split(self.separator))
        self.backing_store.clear()

    def update(self, d):
        for k, v in d.items():
            self[k] = v


class _AddChannelDialog(QtWidgets.QDialog):
    def __init__(self, parent, model):
        QtWidgets.QDialog.__init__(self, parent=parent)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        self.setWindowTitle("Add channels")

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self._model = model
        self._tree_view = QtWidgets.QTreeView()
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)
        self._tree_view.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree_view.setModel(self._model)
        layout.addWidget(self._tree_view)

        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.setCenterButtons(True)
        self._button_box.accepted.connect(self.add_channels)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

    def add_channels(self):
        selection = self._tree_view.selectedIndexes()
        channels = []
        for select in selection:
            key = self._model.index_to_key(select)
            if key is not None:
                channels.append([key, *self._model[key].ref, []])
        self.channels = channels
        self.accept()


class WaveformDock(QtWidgets.QDockWidget):
    def __init__(self, timeout, timer, timer_backoff, ssl_config=None):
        QtWidgets.QDockWidget.__init__(self, "Waveform")
        self.setObjectName("Waveform")
        self.setFeatures(
            self.DockWidgetFeature.DockWidgetMovable | self.DockWidgetFeature.DockWidgetFloatable)

        self._channel_model = Model({})
        self._waveform_model = _WaveformModel()

        self._ddb = None
        self._dump = None

        self._waveform_data = {
            "timescale": 1,
            "stopped_x": None,
            "logs": dict(),
            "data": dict(),
        }

        self._current_dir = os.getcwd()

        self.proxy_client = ProxyClient(self.on_dump_receive,
                                        timeout,
                                        timer,
                                        timer_backoff,
                                        ssl_config)

        grid = LayoutWidget()
        self.setWidget(grid)

        self._menu_btn = QtWidgets.QPushButton()
        self._menu_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogStart))
        grid.addWidget(self._menu_btn, 0, 0)

        self._request_dump_btn = QtWidgets.QToolButton()
        self._request_dump_btn.setToolTip("Fetch analyzer data from device")
        self._request_dump_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_BrowserReload))
        self._request_dump_btn.clicked.connect(
            lambda: asyncio.ensure_future(exc_to_warning(self.proxy_client.trigger_proxy_task())))
        grid.addWidget(self._request_dump_btn, 0, 1)

        self._add_channel_dialog = _AddChannelDialog(self, self._channel_model)
        self._add_channel_dialog.accepted.connect(self._add_channels)

        self._add_btn = QtWidgets.QToolButton()
        self._add_btn.setToolTip("Add channels...")
        self._add_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogListView))
        self._add_btn.clicked.connect(self._add_channel_dialog.open)
        grid.addWidget(self._add_btn, 0, 2)

        self._file_menu = QtWidgets.QMenu()
        self._add_async_action("Open trace...", self.load_trace)
        self._add_async_action("Save trace...", self.save_trace)
        self._add_async_action("Save trace as VCD...", self.save_vcd)
        self._add_async_action("Open channel list...", self.load_channels)
        self._add_async_action("Save channel list...", self.save_channels)
        self._menu_btn.setMenu(self._file_menu)

        self._waveform_view = _WaveformView(self)
        self._waveform_view.setModel(self._waveform_model)
        grid.addWidget(self._waveform_view, 1, 0, colspan=12)

        self._reset_zoom_btn = QtWidgets.QToolButton()
        self._reset_zoom_btn.setToolTip("Reset zoom")
        self._reset_zoom_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarMaxButton))
        self._reset_zoom_btn.clicked.connect(self._waveform_view.resetZoom)
        grid.addWidget(self._reset_zoom_btn, 0, 3)

        self._cursor_control = _CursorTimeControl(self)
        self._waveform_view.cursorMove.connect(self._cursor_control.setDisplayValue)
        self._cursor_control.submit.connect(self._waveform_view.onCursorMove)
        grid.addWidget(self._cursor_control, 0, 4, colspan=6)

    def _add_async_action(self, label, coro):
        action = QtGui.QAction(label, self)
        action.triggered.connect(
            lambda: asyncio.ensure_future(exc_to_warning(coro())))
        self._file_menu.addAction(action)

    def _add_channels(self):
        channels = self._add_channel_dialog.channels
        count = self._waveform_model.rowCount()
        self._waveform_model.extend(channels)
        self._waveform_model.update_data(self._waveform_data['data'],
                                         count,
                                         count + len(channels))

    def on_dump_receive(self, dump):
        self._dump = dump
        decoded_dump = comm_analyzer.decode_dump(dump)
        waveform_data = comm_analyzer.decoded_dump_to_waveform_data(self._ddb, decoded_dump)
        self._waveform_data.update(waveform_data)
        self._channel_model.update(self._waveform_data['logs'])
        self._waveform_model.update_all(self._waveform_data['data'])
        self._waveform_view.setStoppedX(self._waveform_data['stopped_x'])
        self._waveform_view.setTimescale(self._waveform_data['timescale'])
        self._cursor_control.setTimescale(self._waveform_data['timescale'])

    async def load_trace(self):
        try:
            filename = await get_open_file_name(
                self,
                "Load Analyzer Trace",
                self._current_dir,
                "All files (*.*)")
        except asyncio.CancelledError:
            return
        self._current_dir = os.path.dirname(filename)
        try:
            with open(filename, 'rb') as f:
                dump = f.read()
            self.on_dump_receive(dump)
        except:
            logger.error("Failed to open analyzer trace", exc_info=True)

    async def save_trace(self):
        if self._dump is None:
            logger.error("No analyzer trace stored in dashboard, "
                         "try loading from file or fetching from device")
            return
        try:
            filename = await get_save_file_name(
                self,
                "Save Analyzer Trace",
                self._current_dir,
                "All files (*.*)")
        except asyncio.CancelledError:
            return
        self._current_dir = os.path.dirname(filename)
        try:
            with open(filename, 'wb') as f:
                f.write(self._dump)
        except:
            logger.error("Failed to save analyzer trace", exc_info=True)

    async def save_vcd(self):
        if self._dump is None:
            logger.error("No analyzer trace stored in dashboard, "
                         "try loading from file or fetching from device")
            return
        try:
            filename = await get_save_file_name(
                self,
                "Save VCD",
                self._current_dir,
                "All files (*.*)")
        except asyncio.CancelledError:
            return
        self._current_dir = os.path.dirname(filename)
        try:
            decoded_dump = comm_analyzer.decode_dump(self._dump)
            with open(filename, 'w') as f:
                comm_analyzer.decoded_dump_to_vcd(f, self._ddb, decoded_dump)
        except:
            logger.error("Failed to save trace as VCD", exc_info=True)

    async def load_channels(self):
        try:
            filename = await get_open_file_name(
                self,
                "Open channel list",
                self._current_dir,
                "PYON files (*.pyon);;All files (*.*)")
        except asyncio.CancelledError:
            return
        self._current_dir = os.path.dirname(filename)
        try:
            channel_list = pyon.load_file(filename)
            self._waveform_model.import_list(channel_list)
            self._waveform_model.update_all(self._waveform_data['data'])
        except:
            logger.error("Failed to open channel list", exc_info=True)

    async def save_channels(self):
        try:
            filename = await get_save_file_name(
                self,
                "Save channel list",
                self._current_dir,
                "PYON files (*.pyon);;All files (*.*)")
        except asyncio.CancelledError:
            return
        self._current_dir = os.path.dirname(filename)
        try:
            channel_list = self._waveform_model.export_list()
            pyon.store_file(filename, channel_list)
        except:
            logger.error("Failed to save channel list", exc_info=True)

    def _process_ddb(self):
        channel_list = comm_analyzer.get_channel_list(self._ddb)
        self._channel_model.clear()
        self._channel_model.update(channel_list)
        desc = self._ddb.get("core_analyzer")
        if desc is not None:
            addr = desc["host"]
            port_proxy = desc.get("port_proxy", 1385)
            port = desc.get("port", 1386)
            self.proxy_client.update_address(addr, port, port_proxy)
        else:
            self.proxy_client.update_address(None, None, None)

    def init_ddb(self, ddb):
        self._ddb = ddb
        self._process_ddb()
        return ddb

    def notify_ddb(self, mod):
        self._process_ddb()

    async def stop(self):
        if self.proxy_client is not None:
            await self.proxy_client.close()
