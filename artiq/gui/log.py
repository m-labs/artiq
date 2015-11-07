import asyncio
import logging
import time

from quamash import QtGui, QtCore
from pyqtgraph import dockarea, LayoutWidget

from artiq.protocols.sync_struct import Subscriber

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


class _LogModel(QtCore.QAbstractTableModel):
    def __init__(self, parent, init):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.headers = ["Level", "Source", "Time", "Message"]

        self.entries = init
        self.pending_entries = []
        self.depth = 1000
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.timer_tick)
        timer.start(100)

        self.fixed_font = QtGui.QFont()
        self.fixed_font.setFamily("Monospace")

        self.white = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        self.black = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        self.debug_fg = QtGui.QBrush(QtGui.QColor(55, 55, 55))
        self.warning_bg = QtGui.QBrush(QtGui.QColor(255, 255, 180))
        self.error_bg = QtGui.QBrush(QtGui.QColor(255, 150, 150))

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal
                and role == QtCore.Qt.DisplayRole):
            return self.headers[col]
        return None

    def rowCount(self, parent):
        return len(self.entries)

    def columnCount(self, parent):
        return len(self.headers)

    def __delitem__(self, k):
        pass

    def append(self, v):
        self.pending_entries.append(v)

    def insertRows(self, position, rows=1, index=QtCore.QModelIndex()):
        self.beginInsertRows(QtCore.QModelIndex(), position, position+rows-1)
        self.endInsertRows()

    def removeRows(self, position, rows=1, index=QtCore.QModelIndex()):
        self.beginRemoveRows(QtCore.QModelIndex(), position, position+rows-1)
        self.endRemoveRows()

    def timer_tick(self):
        if not self.pending_entries:
            return
        nrows = len(self.entries)
        records = self.pending_entries
        self.pending_entries = []
        self.entries.extend(records)
        self.insertRows(nrows, len(records))
        if len(self.entries) > self.depth:
            start = len(self.entries) - self.depth
            self.entries = self.entries[start:]
            self.removeRows(0, start)

    def data(self, index, role):
        if index.isValid():
            if (role == QtCore.Qt.FontRole
                    and index.column() == 3):
                return self.fixed_font
            elif role == QtCore.Qt.BackgroundRole:
                level = self.entries[index.row()][0]
                if level >= logging.ERROR:
                    return self.error_bg
                elif level >= logging.WARNING:
                    return self.warning_bg
                else:
                    return self.white
            elif role == QtCore.Qt.ForegroundRole:
                level = self.entries[index.row()][0]
                if level <= logging.DEBUG:
                    return self.debug_fg
                else:
                    return self.black
            elif role == QtCore.Qt.DisplayRole:
                v = self.entries[index.row()]
                column = index.column()
                if column == 0:
                    return _level_to_name(v[0])
                elif column == 1:
                    return v[1]
                elif column == 2:
                    return time.strftime("%m/%d %H:%M:%S", time.localtime(v[2]))
                else:
                    return v[3]


class _LogFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, min_level, freetext):
        QSortFilterProxyModel.__init__(self)
        self.min_level = min_level
        self.freetext = freetext

    def filterAcceptsRow(self, sourceRow, sourceParent):
        model = self.sourceModel()

        index = model.index(sourceRow, 0, sourceParent)
        data = model.data(index, QtCore.Qt.DisplayRole)
        accepted_level = getattr(logging, data) >= self.min_level

        if self.freetext:
            index = model.index(sourceRow, 1, sourceParent)
            data_source = model.data(index, QtCore.Qt.DisplayRole)
            index = model.index(sourceRow, 3, sourceParent)
            data_message = model.data(index, QtCore.Qt.DisplayRole)
            accepted_freetext = (self.freetext in data_source
                or self.freetext in data_message)
        else:
            accepted_freetext = True

        return accepted_level and accepted_freetext

    def set_min_level(self, min_level):
        self.min_level = min_level
        self.invalidateFilter()

    def set_freetext(self, freetext):
        self.freetext = freetext
        self.invalidateFilter()


class LogDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Log", size=(1000, 300))

        grid = LayoutWidget()
        self.addWidget(grid)

        grid.addWidget(QtGui.QLabel("Minimum level: "), 0, 0)
        self.filter_level = QtGui.QComboBox()
        self.filter_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_level.setToolTip("Display entries at or above this level")
        grid.addWidget(self.filter_level, 0, 1)
        self.filter_level.currentIndexChanged.connect(
            self.filter_level_changed)
        self.filter_freetext = QtGui.QLineEdit()
        self.filter_freetext.setPlaceholderText("freetext filter...")
        self.filter_freetext.editingFinished.connect(
            self.filter_freetext_changed)
        grid.addWidget(self.filter_freetext, 0, 2)

        self.log = QtGui.QTableView()
        self.log.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.log.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.log.setHorizontalScrollMode(
            QtGui.QAbstractItemView.ScrollPerPixel)
        self.log.setShowGrid(False)
        self.log.setTextElideMode(QtCore.Qt.ElideNone)
        grid.addWidget(self.log, 1, 0, colspan=4)
        self.scroll_at_bottom = False

    async def sub_connect(self, host, port):
        self.subscriber = Subscriber("log", self.init_log_model)
        await self.subscriber.connect(host, port)

    async def sub_close(self):
        await self.subscriber.close()

    def filter_level_changed(self):
        if not hasattr(self, "table_model_filter"):
            return
        self.table_model_filter.set_min_level(
            getattr(logging, self.filter_level.currentText()))

    def filter_freetext_changed(self):
        if not hasattr(self, "table_model_filter"):
            return
        self.table_model_filter.set_freetext(self.filter_freetext.text())

    def rows_inserted_before(self):
        scrollbar = self.log.verticalScrollBar()
        self.scroll_value = scrollbar.value()
        self.scroll_at_bottom = self.scroll_value == scrollbar.maximum()

    def rows_inserted_after(self):
        if self.scroll_at_bottom:
            self.log.scrollToBottom()

    # HACK:
    # Qt intermittently likes to scroll back to the top when rows are removed.
    # Work around this by restoring the scrollbar to the previously memorized
    # position, after the removal.
    # Note that this works because _LogModel always does the insertion right
    # before the removal.
    def rows_removed(self):
        if self.scroll_at_bottom:
            self.log.scrollToBottom()
        else:
            scrollbar = self.log.verticalScrollBar()
            scrollbar.setValue(self.scroll_value)

    def init_log_model(self, init):
        self.table_model = _LogModel(self.log, init)
        self.table_model_filter = _LogFilterProxyModel(
            getattr(logging, self.filter_level.currentText()),
            self.filter_freetext.text())
        self.table_model_filter.setSourceModel(self.table_model)
        self.log.setModel(self.table_model_filter)
        self.table_model_filter.rowsAboutToBeInserted.connect(self.rows_inserted_before)
        self.table_model_filter.rowsInserted.connect(self.rows_inserted_after)
        self.table_model_filter.rowsRemoved.connect(self.rows_removed)
        return self.table_model

    def save_state(self):
        return {"min_level_idx": self.filter_level.currentIndex()}

    def restore_state(self, state):
        try:
            idx = state["min_level_idx"]
        except KeyError:
            pass
        else:
            self.filter_level.setCurrentIndex(idx)
