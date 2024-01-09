from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt

from sipyco.sync_struct import Subscriber
from sipyco.pc_rpc import AsyncioClient
from sipyco import pyon

from artiq.tools import exc_to_warning
from artiq.gui.tools import LayoutWidget, get_open_file_name, get_save_file_name
from artiq.gui.models import DictSyncTreeSepModel, LocalModelManager
from artiq.gui.dndwidgets import DragDropSplitter, VDragScrollArea
from artiq.coredevice import comm_analyzer
from artiq.coredevice.comm_analyzer import WaveformType

import os
import numpy as np
import itertools
import bisect
import pyqtgraph as pg
import asyncio
import logging
import math
import struct

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


class WaveformArea(QtWidgets.QWidget):
    cursorMoved = QtCore.pyqtSignal(float)

    def __init__(self, parent, state, channels_mgr):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self._state = state
        self._channels_mgr = channels_mgr

        self._cursor_visible = True
        self._cursor_x_pos = 0

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self._ref_axis = pg.PlotWidget()
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
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        layout.addWidget(scroll_area)

        self._splitter = DragDropSplitter(parent=scroll_area)
        self._splitter.setHandleWidth(1)
        scroll_area.setWidget(self._splitter)

    def _add_waveform(self, channel, waveform_type):
        num_channels = self._splitter.count()
        self._splitter.setFixedHeight(
            (num_channels + 1) * Waveform.PREF_HEIGHT)
        cw = waveform_type(channel, self._state, parent=self._splitter)
        self._splitter.addWidget(cw)

        action = QtWidgets.QAction("Toggle cursor visible", cw)
        action.triggered.connect(self._on_toggle_cursor)
        cw.addAction(action)
        action = QtWidgets.QAction("Delete waveform", cw)
        action.triggered.connect(lambda: self._remove_channel(cw))
        cw.addAction(action)
        action = QtWidgets.QAction("Delete all", cw)
        action.triggered.connect(self.clear_channels)
        cw.addAction(action)
        action = QtWidgets.QAction("Reset waveform heights", cw)
        action.triggered.connect(self._splitter.resetSizes)
        cw.addAction(action)

        cw.cursorMoved.connect(lambda x: self.on_cursor_move(x))
        cw.cursorMoved.connect(self.cursorMoved.emit)

        cw.setXLink(self._ref_vb)
        cw.extract_data_from_state()
        cw.display()
        cw.on_cursor_move(self._cursor_x_pos)
        cw.update_x_max()

    async def _add_waveform_task(self):
        dialog = _AddChannelDialog(self, self._channels_mgr)
        fut = asyncio.Future()

        def on_accept(s):
            fut.set_result(s)
        dialog.accepted.connect(on_accept)
        dialog.open()
        channels = await fut
        self.update_channels(channels)

    def update_channels(self, channel_list):
        type_map = {
            WaveformType.BIT: BitWaveform,
            WaveformType.VECTOR: BitVectorWaveform,
            WaveformType.ANALOG: AnalogWaveform,
            WaveformType.LOG: LogWaveform
        }
        for channel in channel_list:
            ty = channel[1][1]
            waveform_type = type_map[ty]
            self._add_waveform(channel, waveform_type)

    def get_channels(self):
        channels = []
        for i in range(self._splitter.count()):
            cw = self._splitter.widget(i)
            channels.append(cw.channel)
        return channels

    def _remove_channel(self, cw):
        num_channels = self._splitter.count() - 1
        cw.deleteLater()
        self._splitter.setFixedHeight(num_channels * Waveform.PREF_HEIGHT)
        self._splitter.refresh()

    def clear_channels(self):
        for i in reversed(range(self._splitter.count())):
            cw = self._splitter.widget(i)
            self._remove_channel(cw)

    def on_add_channel_click(self):
        asyncio.ensure_future(exc_to_warning(self._add_waveform_task()))

    def on_trace_update(self):
        self._top.setScale(1e-12 * self._state["timescale"])
        for i in range(self._splitter.count()):
            cw = self._splitter.widget(i)
            cw.extract_data_from_state()
            cw.display()
            cw.on_cursor_move(self._cursor_x_pos)
            cw.update_x_max()
        maximum = self._state["stopped_x"]
        self._ref_axis.setLimits(xMax=maximum)
        self._ref_axis.setRange(xRange=(0, maximum))

    def on_cursor_move(self, x):
        self._cursor_x_pos = x
        for i in range(self._splitter.count()):
            cw = self._splitter.widget(i)
            cw.on_cursor_move(x)

    def _on_toggle_cursor(self):
        self._cursor_visible = not self._cursor_visible
        for i in range(self._splitter.count()):
            cw = self._splitter.widget(i)
            cw.set_cursor_visible(self._cursor_visible)


class WaveformProxyClient:
    def __init__(self, state, loop):
        self._state = state
        self._loop = loop

        self.devices_sub = None
        self.rpc_client = AsyncioClient()
        self.proxy_receiver = None

        self._proxy_addr = None
        self._proxy_port = None
        self._proxy_port_ctl = None
        self._on_sub_reconnect = asyncio.Event()
        self._on_rpc_reconnect = asyncio.Event()
        self._reconnect_rpc_task = None
        self._reconnect_receiver_task = None

    async def trigger_proxy_task(self):
        try:
            if self.rpc_client.get_rpc_id()[0] is None:
                raise AttributeError("Unable to identify RPC target. Is analyzer proxy connected?")
            asyncio.ensure_future(self.rpc_client.trigger())
        except Exception as e:
            logger.warning("Failed to pull from device: %s", e)

    def update_address(self, addr, port, port_control):
        self._proxy_addr = addr
        self._proxy_port = port
        self._proxy_port_ctl = port_control
        self._on_rpc_reconnect.set()
        self._on_sub_reconnect.set()

    # Proxy client connections
    async def start(self, server, port):
        try:
            await self.devices_sub.connect(server, port)
            self._reconnect_rpc_task = asyncio.ensure_future(
                self.reconnect_rpc(), loop=self._loop)
            self._reconnect_receiver_task = asyncio.ensure_future(
                self.reconnect_receiver(), loop=self._loop)
        except Exception as e:
            logger.error("Failed to connect to master: %s", e)

    async def reconnect_rpc(self):
        try:
            while True:
                await self._on_rpc_reconnect.wait()
                self._on_rpc_reconnect.clear()
                logger.info("Attempting analyzer proxy RPC connection...")
                try:
                    await self.rpc_client.connect_rpc(self._proxy_addr,
                                                      self._proxy_port_ctl,
                                                      "coreanalyzer_proxy_control")
                except Exception:
                    logger.info("Analyzer proxy RPC timed out, trying again...")
                    await asyncio.sleep(5)
                    self._on_rpc_reconnect.set()
                else:
                    logger.info("RPC connected to analyzer proxy on %s/%s",
                                self._proxy_addr, self._proxy_port_ctl)
        except asyncio.CancelledError:
            pass

    async def reconnect_receiver(self):
        try:
            while True:
                await self._on_sub_reconnect.wait()
                self._on_sub_reconnect.clear()
                logger.info("Setting up analyzer proxy receiver...")
                try:
                    await self.proxy_receiver.connect(
                        self._proxy_addr, self._proxy_port)
                except Exception:
                    logger.info("Failed to set up analyzer proxy receiver, reconnecting...")
                    await asyncio.sleep(5)
                    self._on_sub_reconnect.set()
                else:
                    logger.info("Receiving from analyzer proxy on %s:%s",
                                self._proxy_addr, self._proxy_port)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        try:
            self._reconnect_rpc_task.cancel()
            self._reconnect_receiver_task.cancel()
            await asyncio.wait_for(self._reconnect_rpc_task, None)
            await asyncio.wait_for(self._reconnect_receiver_task, None)
            await self.devices_sub.close()
            self.rpc_client.close_rpc()
            await self.proxy_receiver.close()
        except Exception as e:
            logger.error("Error occurred while closing proxy connections: %s",
                         e, exc_info=True)


class _CursorTimeControl(QtWidgets.QLineEdit):
    submit = QtCore.pyqtSignal(float)
    PRECISION = 15

    def __init__(self, parent, state):
        QtWidgets.QLineEdit.__init__(self, parent=parent)
        self._value = 0
        self._state = state
        self.display_value(0)
        self.textChanged.connect(self._on_text_change)
        self.returnPressed.connect(self._on_return_press)

    def _on_text_change(self, text):
        try:
            self._value = pg.siEval(text) * (1e12 / self._state["timescale"])
        except Exception:
            # invalid text entry is ignored, resets to valid value on return pressed
            pass

    def display_value(self, val):
        t = pg.siFormat(val * 1e-12 * self._state["timescale"], suffix="s",
                        allowUnicode=False,
                        precision=self.PRECISION)
        self.setText(t)

    def _on_return_press(self):
        self.submit.emit(self._value)
        self.display_value(self._value)
        self.clearFocus()


class WaveformDock(QtWidgets.QDockWidget):
    traceDataChanged = QtCore.pyqtSignal()

    def __init__(self, loop=None):
        QtWidgets.QDockWidget.__init__(self, "Waveform")
        self.setObjectName("Waveform")
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)

        self._channels_mgr = LocalModelManager(Model)
        self._channels_mgr.init({})

        self._devices = None
        self._dump = None

        self._state = {
            "timescale": 1,
            "stopped_x": None,
            "logs": dict(),
            "data": dict(),
        }

        self._current_dir = "c://"

        self.proxy_client = WaveformProxyClient(self._state, loop)
        devices_sub = Subscriber("devices", self.init_ddb, self.update_ddb)

        proxy_receiver = comm_analyzer.AnalyzerProxyReceiver(
            self.on_dump_receive)
        self.proxy_client.devices_sub = devices_sub
        self.proxy_client.proxy_receiver = proxy_receiver

        grid = LayoutWidget()
        self.setWidget(grid)

        self._menu_btn = QtWidgets.QPushButton()
        self._menu_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_FileDialogStart))
        grid.addWidget(self._menu_btn, 0, 0)

        self._request_dump_btn = QtWidgets.QToolButton()
        self._request_dump_btn.setToolTip("Trigger proxy")
        self._request_dump_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_BrowserReload))
        grid.addWidget(self._request_dump_btn, 0, 1)
        self._request_dump_btn.clicked.connect(
            lambda: asyncio.ensure_future(self.proxy_client.trigger_proxy_task()))

        self._waveform_area = WaveformArea(self, self._state,
                                           self._channels_mgr)
        self.traceDataChanged.connect(self._waveform_area.on_trace_update)
        self.traceDataChanged.connect(self._update_log_channels)
        grid.addWidget(self._waveform_area, 2, 0, colspan=12)

        self._add_btn = QtWidgets.QToolButton()
        self._add_btn.setToolTip("Add channels...")
        self._add_btn.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_FileDialogListView))
        grid.addWidget(self._add_btn, 0, 2)
        self._add_btn.clicked.connect(self._waveform_area.on_add_channel_click)

        self._cursor_control = _CursorTimeControl(parent=self, state=self._state)
        grid.addWidget(self._cursor_control, 0, 3, colspan=3)
        self._cursor_control.submit.connect(
            self._waveform_area.on_cursor_move)
        self._waveform_area.cursorMoved.connect(self._cursor_control.display_value)

        self._file_menu = QtWidgets.QMenu()
        self._add_async_action("Open trace...", self.load_trace)
        self._add_async_action("Save trace...", self.save_trace)
        self._add_async_action("Save VCD...", self.save_vcd)
        self._add_async_action("Open list of channels...", self.load_channels)
        self._add_async_action("Save list of channels...", self.save_channels)
        self._menu_btn.setMenu(self._file_menu)

    def _add_async_action(self, label, coro):
        action = QtWidgets.QAction(label, self)
        action.triggered.connect(
            lambda: asyncio.ensure_future(exc_to_warning(coro())))
        self._file_menu.addAction(action)

    def _update_log_channels(self):
        for log in self._state['logs']:
            self._channels_mgr.update({
                "action": "setitem",
                "path": "",
                "key": log,
                "value": (0, "log")
            })

    def on_dump_receive(self, *args):
        header = comm_analyzer.decode_header_from_receiver(*args)
        decoded_dump = comm_analyzer.decode_dump_loop(*header)
        ddb = self._ddb
        trace = comm_analyzer.decoded_dump_to_dict(ddb, decoded_dump)
        self._state.update(trace)
        self._dump = args
        self.traceDataChanged.emit()

    def on_dump_read(self, dump):
        endian_byte = dump[0]
        if endian_byte == ord("E"):
            endian = '>'
        elif endian_byte == ord("e"):
            endian = '<'
        else:
            logger.warning("first byte is not endian")
            raise ValueError
        payload_length_word = dump[1:5]
        payload_length = struct.unpack(endian + "I", payload_length_word)[0]
        data = dump[5:]
        self.on_dump_receive(endian, payload_length, data)

    def _decode_dump(self):
        dump = self._dump
        header = comm_analyzer.decode_header_from_receiver(*dump)
        return comm_analyzer.decode_dump_loop(*header)

    def _dump_header(self, endian, payload_length):
        payload_length_word = struct.pack(endian + "I", payload_length)
        if endian == ">":
            endian_byte = b"E"
        else:
            endian_byte = b"e"
        return endian_byte + payload_length_word

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
            self.on_dump_read(dump)
        except Exception as e:
            logger.error("Failed to open analyzer trace: %s", e)

    async def save_trace(self):
        dump = self._dump
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
                f.write(self._dump_header(dump[0], dump[1]))
                f.write(dump[2])

        except Exception as e:
            logger.error("Failed to save analyzer trace: %s", e)

    async def save_vcd(self):
        ddb = self._ddb
        dump = self._dump
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
            with open(filename, 'w') as f:
                decoded_dump = comm_analyzer.decode_dump(dump)
                comm_analyzer.decoded_dump_to_vcd(f, ddb, decoded_dump)
        except Exception as e:
            logger.error("Failed to save as VCD: %s", e)
        finally:
            logger.info("Finished writing to VCD.")

    async def load_channels(self):
        try:
            filename = await get_open_file_name(
                self,
                "Open List of Channels",
                self._current_dir,
                "All files (*.*)")
        except asyncio.CancelledError:
            return
        self._current_dir = os.path.dirname(filename)
        try:
            channel_list = pyon.load_file(filename)
            self._waveform_area.clear_channels()
            self._waveform_area.update_channels(channel_list)
        except Exception as e:
            logger.error("Failed to open list of channels: %s", e)

    async def save_channels(self):
        try:
            filename = await get_save_file_name(
                self,
                "Load Analyzer Trace",
                self._current_dir,
                "All files (*.*)")
        except asyncio.CancelledError:
            return
        self._current_dir = os.path.dirname(filename)
        try:
            obj = self._waveform_area.get_channels()
            pyon.store_file(filename, obj)
        except Exception as e:
            logger.error("Failed to open analyzer trace: %s", e)

    # DeviceDB subscriber callbacks
    def init_ddb(self, ddb):
        self._ddb = ddb

    def update_ddb(self, mod):
        devices = self._ddb
        addr = None
        self._channels_mgr.init(comm_analyzer.get_channel_list(devices))
        for name, desc in devices.items():
            if isinstance(desc, dict):
                if desc["type"] == "controller" and name == "core_analyzer":
                    addr = desc["host"]
                    port = desc.get("port_proxy", 1385)
                    port_control = desc.get("port_proxy_control", 1386)
        if addr is not None:
            self.proxy_client.update_address(addr, port, port_control)
