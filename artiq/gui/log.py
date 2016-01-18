import asyncio
import logging
import time
import re
from functools import partial

from quamash import QtGui, QtCore
from pyqtgraph import dockarea, LayoutWidget

from artiq.gui.tools import log_level_to_name

try:
    QSortFilterProxyModel = QtCore.QSortFilterProxyModel
except AttributeError:
    QSortFilterProxyModel = QtGui.QSortFilterProxyModel


def _make_wrappable(row, width=30):
    level, source, time, msg = row
    msg = re.sub("(\\S{{{}}})".format(width), "\\1\u200b", msg)
    return [level, source, time, msg]


class Model(QtCore.QAbstractTableModel):
    def __init__(self, init):
        QtCore.QAbstractTableModel.__init__(self)

        self.headers = ["Level", "Source", "Time", "Message"]

        self.entries = list(map(_make_wrappable, init))
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
        self.pending_entries.append(_make_wrappable(v))

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
                    return log_level_to_name(v[0])
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


class _LogDock(dockarea.Dock):
    def __init__(self, manager, name, log_sub):
        dockarea.Dock.__init__(self, name, label="Log")
        self.setMinimumSize(QtCore.QSize(850, 450))

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

        scrollbottom = QtGui.QToolButton()
        scrollbottom.setToolTip("Scroll to bottom")
        scrollbottom.setIcon(QtGui.QApplication.style().standardIcon(
            QtGui.QStyle.SP_ArrowDown))
        grid.addWidget(scrollbottom, 0, 3)
        scrollbottom.clicked.connect(self.scroll_to_bottom)
        newdock = QtGui.QToolButton()
        newdock.setToolTip("Create new log dock")
        newdock.setIcon(QtGui.QApplication.style().standardIcon(
            QtGui.QStyle.SP_FileDialogNewFolder))
        # note the lambda, the default parameter is overriden otherwise
        newdock.clicked.connect(lambda: manager.create_new_dock())
        grid.addWidget(newdock, 0, 4)
        grid.layout.setColumnStretch(2, 1)

        self.log = QtGui.QTableView()
        self.log.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.log.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.log.horizontalHeader().setStretchLastSection(True)
        self.log.verticalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.log.verticalHeader().hide()
        self.log.setHorizontalScrollMode(
            QtGui.QAbstractItemView.ScrollPerPixel)
        self.log.setVerticalScrollMode(
            QtGui.QAbstractItemView.ScrollPerPixel)
        self.log.setShowGrid(False)
        self.log.setTextElideMode(QtCore.Qt.ElideNone)
        grid.addWidget(self.log, 1, 0, colspan=5)
        self.scroll_at_bottom = False
        self.scroll_value = 0

        log_sub.add_setmodel_callback(self.set_model)

    def filter_level_changed(self):
        if not hasattr(self, "table_model_filter"):
            return
        self.table_model_filter.set_min_level(
            getattr(logging, self.filter_level.currentText()))

    def filter_freetext_changed(self):
        if not hasattr(self, "table_model_filter"):
            return
        self.table_model_filter.set_freetext(self.filter_freetext.text())

    def scroll_to_bottom(self):
        self.log.scrollToBottom()

    def rows_inserted_before(self):
        scrollbar = self.log.verticalScrollBar()
        self.scroll_value = scrollbar.value()
        self.scroll_at_bottom = self.scroll_value == scrollbar.maximum()

    def rows_inserted_after(self):
        if self.scroll_at_bottom:
            self.log.scrollToBottom()

        # HACK:
        # If we don't do this, after we first add some rows, the "Time"
        # column gets undersized and the text in it gets wrapped.
        # We can call self.log.resizeColumnsToContents(), which fixes
        # that problem, but now the message column is too large and
        # a horizontal scrollbar appears.
        # This is almost certainly a Qt layout bug.
        self.log.horizontalHeader().reset()

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

    def set_model(self, model):
        self.table_model = model
        self.table_model_filter = _LogFilterProxyModel(
            getattr(logging, self.filter_level.currentText()),
            self.filter_freetext.text())
        self.table_model_filter.setSourceModel(self.table_model)
        self.log.setModel(self.table_model_filter)
        self.table_model_filter.rowsAboutToBeInserted.connect(self.rows_inserted_before)
        self.table_model_filter.rowsInserted.connect(self.rows_inserted_after)
        self.table_model_filter.rowsRemoved.connect(self.rows_removed)

    def save_state(self):
        return {
            "min_level_idx": self.filter_level.currentIndex(),
            "freetext_filter": self.filter_freetext.text()
        }

    def restore_state(self, state):
        try:
            idx = state["min_level_idx"]
        except KeyError:
            pass
        else:
            self.filter_level.setCurrentIndex(idx)

        try:
            freetext = state["freetext_filter"]
        except KeyError:
            pass
        else:
            self.filter_freetext.setText(freetext)
            # Note that editingFinished is not emitted when calling setText,
            # (unlike currentIndexChanged) so we need to call the callback
            # manually here, unlike for the combobox.
            self.filter_freetext_changed()


class LogDockManager:
    def __init__(self, dock_area, log_sub):
        self.dock_area = dock_area
        self.log_sub = log_sub
        self.docks = dict()

    def create_new_dock(self, add_to_area=True):
        n = 0
        name = "log0"
        while name in self.docks:
            n += 1
            name = "log" + str(n)

        dock = _LogDock(self, name, self.log_sub)
        self.docks[name] = dock
        if add_to_area:
            self.dock_area.floatDock(dock)
        dock.sigClosed.connect(partial(self.on_dock_closed, name))
        self.update_closable()
        return dock

    def on_dock_closed(self, name):
        del self.docks[name]
        self.update_closable()

    def update_closable(self):
        closable = len(self.docks) > 1
        for dock in self.docks.values():
            dock.setClosable(closable)

    def save_state(self):
        return {name: dock.save_state() for name, dock in self.docks.items()}

    def restore_state(self, state):
        if self.docks:
            raise NotImplementedError
        for name, dock_state in state.items():
            dock = _LogDock(self, name, self.log_sub)
            dock.restore_state(dock_state)
            self.dock_area.addDock(dock)
            self.docks[name] = dock

    def first_log_dock(self):
        if self.docks:
            return None
        dock = self.create_new_dock(False)
        return dock
