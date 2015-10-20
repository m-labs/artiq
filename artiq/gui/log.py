import asyncio
import logging
import time

from quamash import QtGui, QtCore
from pyqtgraph import dockarea, LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import ListSyncModel

try:
    QSortFilterProxyModel = QtCore.QSortFilterProxyModel
except AttributeError:
    QSortFilterProxyModel = QtGui.QSortFilterProxyModel


def _level_to_name(level):
    if level >= logging.CRITICAL:
        return "CRITICAL"
    if level >= logging.ERROR:
        return "ERROR"
    if level >= logging.WARNING:
        return "WARNING"
    if level >= logging.INFO:
        return "INFO"
    return "DEBUG"


class _LogModel(ListSyncModel):
    def __init__(self, parent, init):
        ListSyncModel.__init__(self,
            ["Level", "Source", "Time", "Message"],
            parent, init)
        self.fixed_font = QtGui.QFont()
        self.fixed_font.setFamily("Monospace")

        self.white = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        self.black = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        self.debug_fg = QtGui.QBrush(QtGui.QColor(55, 55, 55))
        self.warning_bg = QtGui.QBrush(QtGui.QColor(255, 255, 180))
        self.error_bg = QtGui.QBrush(QtGui.QColor(255, 150, 150))

    def data(self, index, role):
        if (role == QtCore.Qt.FontRole and index.isValid()
                and index.column() == 3):
            return self.fixed_font
        elif role == QtCore.Qt.BackgroundRole and index.isValid():
            level = self.backing_store[index.row()][0]
            if level >= logging.ERROR:
                return self.error_bg
            elif level >= logging.WARNING:
                return self.warning_bg
            else:
                return self.white
        elif role == QtCore.Qt.ForegroundRole and index.isValid():
            level = self.backing_store[index.row()][0]
            if level <= logging.DEBUG:
                return self.debug_fg
            else:
                return self.black
        else:
            return ListSyncModel.data(self, index, role)

    def convert(self, v, column):
        if column == 0:
            return _level_to_name(v[0])
        elif column == 1:
            return v[1]
        elif column == 2:
            return time.strftime("%m/%d %H:%M:%S", time.localtime(v[2]))
        else:
            return v[3]


class _LevelFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, min_level):
        QSortFilterProxyModel.__init__(self)
        self.min_level = min_level

    def filterAcceptsRow(self, sourceRow, sourceParent):
        model = self.sourceModel()
        index = model.index(sourceRow, 0, sourceParent)
        data = model.data(index, QtCore.Qt.DisplayRole)
        return getattr(logging, data) >= self.min_level

    def set_min_level(self, min_level):
        self.min_level = min_level
        self.invalidateFilter()


class LogDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Log", size=(1000, 300))

        grid = LayoutWidget()
        self.addWidget(grid)

        grid.addWidget(QtGui.QLabel("Minimum level: "), 0, 0)
        grid.layout.setColumnStretch(0, 0)
        grid.layout.setColumnStretch(1, 0)
        grid.layout.setColumnStretch(2, 1)
        self.filterbox = QtGui.QComboBox()
        for item in "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL":
            self.filterbox.addItem(item)
        self.filterbox.setToolTip("Display entries at or above this level")
        grid.addWidget(self.filterbox, 0, 1)
        self.filterbox.currentIndexChanged.connect(self.filter_changed)

        self.log = QtGui.QTableView()
        self.log.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.log.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.log.setHorizontalScrollMode(
            QtGui.QAbstractItemView.ScrollPerPixel)
        self.log.setShowGrid(False)
        self.log.setTextElideMode(QtCore.Qt.ElideNone)
        grid.addWidget(self.log, 1, 0, colspan=3)
        self.scroll_at_bottom = False

    async def sub_connect(self, host, port):
        self.subscriber = Subscriber("log", self.init_log_model)
        await self.subscriber.connect(host, port)

    async def sub_close(self):
        await self.subscriber.close()

    def filter_changed(self):
        self.table_model_filter.set_min_level(
            getattr(logging, self.filterbox.currentText()))

    def rows_inserted_before(self):
        scrollbar = self.log.verticalScrollBar()
        self.scroll_at_bottom = scrollbar.value() == scrollbar.maximum()

    def rows_inserted_after(self):
        if self.scroll_at_bottom:
            self.log.scrollToBottom()

    def init_log_model(self, init):
        table_model = _LogModel(self.log, init)
        self.table_model_filter = _LevelFilterProxyModel(
            getattr(logging, self.filterbox.currentText()))
        self.table_model_filter.setSourceModel(table_model)
        self.log.setModel(self.table_model_filter)
        self.table_model_filter.rowsAboutToBeInserted.connect(self.rows_inserted_before)
        self.table_model_filter.rowsInserted.connect(self.rows_inserted_after)
        return table_model

    def save_state(self):
        return {"min_level_idx": self.filterbox.currentIndex()}

    def restore_state(self, state):
        try:
            idx = state["min_level_idx"]
        except KeyError:
            pass
        else:
            self.filterbox.setCurrentIndex(idx)
