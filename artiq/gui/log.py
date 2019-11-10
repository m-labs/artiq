import asyncio
import logging
import time
import re
from functools import partial

from PyQt5 import QtCore, QtGui, QtWidgets

from sipyco.logging_tools import SourceFilter
from artiq.gui.tools import (LayoutWidget, log_level_to_name,
                             QDockWidgetCloseDetect)


class _ModelItem:
    def __init__(self, parent, row):
        self.parent = parent
        self.row = row
        self.children_by_row = []


class _Model(QtCore.QAbstractItemModel):
    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)

        self.headers = ["Source", "Message"]
        self.children_by_row = []

        self.entries = []
        self.pending_entries = []
        self.depth = 1000
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.timer_tick)
        timer.start(100)

        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

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
        if parent.isValid():
            item = parent.internalPointer()
            return len(item.children_by_row)
        else:
            return len(self.entries)

    def columnCount(self, parent):
        return len(self.headers)

    def append(self, v):
        severity, source, timestamp, message = v
        self.pending_entries.append((severity, source, timestamp,
                                     message.splitlines()))

    def clear(self):
        self.beginRemoveRows(QtCore.QModelIndex(), 0, len(self.entries)-1)
        self.entries.clear()
        self.children_by_row.clear()
        self.endRemoveRows()

    def timer_tick(self):
        if not self.pending_entries:
            return
        nrows = len(self.entries)
        records = self.pending_entries
        self.pending_entries = []

        self.beginInsertRows(QtCore.QModelIndex(), nrows, nrows+len(records)-1)
        self.entries.extend(records)
        for rec in records:
            item = _ModelItem(self, len(self.children_by_row))
            self.children_by_row.append(item)
            for i in range(len(rec[3])-1):
                item.children_by_row.append(_ModelItem(item, i))
        self.endInsertRows()

        if len(self.entries) > self.depth:
            start = len(self.entries) - self.depth
            self.beginRemoveRows(QtCore.QModelIndex(), 0, start-1)
            self.entries = self.entries[start:]
            self.children_by_row = self.children_by_row[start:]
            for child in self.children_by_row:
                child.row -= start
            self.endRemoveRows()

    def index(self, row, column, parent):
        if parent.isValid():
            parent_item = parent.internalPointer()
            return self.createIndex(row, column,
                                    parent_item.children_by_row[row])
        else:
            return self.createIndex(row, column, self.children_by_row[row])

    def parent(self, index):
        if index.isValid():
            parent = index.internalPointer().parent
            if parent is self:
                return QtCore.QModelIndex()
            else:
                return self.createIndex(parent.row, 0, parent)
        else:
            return QtCore.QModelIndex()

    def full_entry(self, index):
        if not index.isValid():
            return
        item = index.internalPointer()
        if item.parent is self:
            msgnum = item.row
        else:
            msgnum = item.parent.row
        return self.entries[msgnum][3]

    def data(self, index, role):
        if not index.isValid():
            return

        item = index.internalPointer()
        if item.parent is self:
            msgnum = item.row
        else:
            msgnum = item.parent.row

        if role == QtCore.Qt.FontRole and index.column() == 1:
            return self.fixed_font
        elif role == QtCore.Qt.BackgroundRole:
            level = self.entries[msgnum][0]
            if level >= logging.ERROR:
                return self.error_bg
            elif level >= logging.WARNING:
                return self.warning_bg
            else:
                return self.white
        elif role == QtCore.Qt.ForegroundRole:
            level = self.entries[msgnum][0]
            if level <= logging.DEBUG:
                return self.debug_fg
            else:
                return self.black
        elif role == QtCore.Qt.DisplayRole:
            v = self.entries[msgnum]
            column = index.column()
            if item.parent is self:
                if column == 0:
                    return v[1]
                else:
                    return v[3][0]
            else:
                if column == 0:
                    return ""
                else:
                    return v[3][item.row+1]
        elif role == QtCore.Qt.ToolTipRole:
            v = self.entries[msgnum]
            if item.parent is self:
                lineno = 0
            else:
                lineno = item.row + 1
            return (log_level_to_name(v[0]) + ", " +
                time.strftime("%m/%d %H:%M:%S", time.localtime(v[2])) +
                "\n" + v[3][lineno])


class LogDock(QDockWidgetCloseDetect):
    def __init__(self, manager, name):
        QDockWidgetCloseDetect.__init__(self, "Log")
        self.setObjectName(name)

        grid = LayoutWidget()
        self.setWidget(grid)

        grid.addWidget(QtWidgets.QLabel("Minimum level: "), 0, 0)
        self.filter_level = QtWidgets.QComboBox()
        self.filter_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_level.setToolTip("Receive entries at or above this level")
        grid.addWidget(self.filter_level, 0, 1)
        self.filter_freetext = QtWidgets.QLineEdit()
        self.filter_freetext.setPlaceholderText("freetext filter...")
        self.filter_freetext.setToolTip("Receive entries containing this text")
        grid.addWidget(self.filter_freetext, 0, 2)

        scrollbottom = QtWidgets.QToolButton()
        scrollbottom.setToolTip("Scroll to bottom")
        scrollbottom.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_ArrowDown))
        grid.addWidget(scrollbottom, 0, 3)
        scrollbottom.clicked.connect(self.scroll_to_bottom)

        clear = QtWidgets.QToolButton()
        clear.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_DialogResetButton))
        grid.addWidget(clear, 0, 4)
        clear.clicked.connect(lambda: self.model.clear())

        if manager:
            newdock = QtWidgets.QToolButton()
            newdock.setToolTip("Create new log dock")
            newdock.setIcon(QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_FileDialogNewFolder))
            # note the lambda, the default parameter is overriden otherwise
            newdock.clicked.connect(lambda: manager.create_new_dock())
            grid.addWidget(newdock, 0, 5)
        grid.layout.setColumnStretch(2, 1)

        self.log = QtWidgets.QTreeView()
        self.log.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.log.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.log.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        grid.addWidget(self.log, 1, 0, colspan=6 if manager else 5)
        self.scroll_at_bottom = False
        self.scroll_value = 0

        self.log.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        copy_action = QtWidgets.QAction("Copy entry to clipboard", self.log)
        copy_action.triggered.connect(self.copy_to_clipboard)
        self.log.addAction(copy_action)
        clear_action = QtWidgets.QAction("Clear", self.log)
        clear_action.triggered.connect(lambda: self.model.clear())
        self.log.addAction(clear_action)

        # If Qt worked correctly, this would be nice to have. Alas, resizeSections
        # is broken when the horizontal scrollbar is enabled.
        # sizeheader_action = QtWidgets.QAction("Resize header", self.log)
        # sizeheader_action.triggered.connect(
        #     lambda: self.log.header().resizeSections(QtWidgets.QHeaderView.ResizeToContents))
        # self.log.addAction(sizeheader_action)

        cw = QtGui.QFontMetrics(self.font()).averageCharWidth()
        self.log.header().resizeSection(0, 26*cw)

        self.model = _Model()
        self.log.setModel(self.model)
        self.model.rowsAboutToBeInserted.connect(self.rows_inserted_before)
        self.model.rowsInserted.connect(self.rows_inserted_after)
        self.model.rowsRemoved.connect(self.rows_removed)

    def append_message(self, msg):
        min_level = getattr(logging, self.filter_level.currentText())
        freetext = self.filter_freetext.text()

        accepted_level = msg[0] >= min_level

        if freetext:
            data_source = msg[1]
            data_message = msg[3]
            accepted_freetext = (freetext in data_source
                or any(freetext in m for m in data_message))
        else:
            accepted_freetext = True

        if accepted_level and accepted_freetext:
            self.model.append(msg)

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
    # Qt intermittently likes to scroll back to the top when rows are removed.
    # Work around this by restoring the scrollbar to the previously memorized
    # position, after the removal.
    # Note that this works because _LogModel always does the insertion right
    # before the removal.
    # TODO: check if this is still required after moving to QTreeView
    def rows_removed(self):
        if self.scroll_at_bottom:
            self.log.scrollToBottom()
        else:
            scrollbar = self.log.verticalScrollBar()
            scrollbar.setValue(self.scroll_value)

    def copy_to_clipboard(self):
        idx = self.log.selectedIndexes()
        if idx:
            entry = "\n".join(self.model.full_entry(idx[0]))
            QtWidgets.QApplication.clipboard().setText(entry)

    def save_state(self):
        return {
            "min_level_idx": self.filter_level.currentIndex(),
            "freetext_filter": self.filter_freetext.text(),
            "header": bytes(self.log.header().saveState())
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

        try:
            header = state["header"]
        except KeyError:
            pass
        else:
            self.log.header().restoreState(QtCore.QByteArray(header))


class LogDockManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.docks = dict()

    def append_message(self, msg):
        for dock in self.docks.values():
            dock.append_message(msg)

    def create_new_dock(self, add_to_area=True):
        n = 0
        name = "log0"
        while name in self.docks:
            n += 1
            name = "log" + str(n)

        dock = LogDock(self, name)
        self.docks[name] = dock
        if add_to_area:
            self.main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
            dock.setFloating(True)
        dock.sigClosed.connect(partial(self.on_dock_closed, name))
        self.update_closable()
        return dock

    def on_dock_closed(self, name):
        dock = self.docks[name]
        dock.deleteLater()
        del self.docks[name]
        self.update_closable()

    def update_closable(self):
        flags = (QtWidgets.QDockWidget.DockWidgetMovable |
                 QtWidgets.QDockWidget.DockWidgetFloatable)
        if len(self.docks) > 1:
            flags |= QtWidgets.QDockWidget.DockWidgetClosable
        for dock in self.docks.values():
            dock.setFeatures(flags)

    def save_state(self):
        return {name: dock.save_state() for name, dock in self.docks.items()}

    def restore_state(self, state):
        if self.docks:
            raise NotImplementedError
        for name, dock_state in state.items():
            dock = LogDock(self, name)
            self.docks[name] = dock
            dock.restore_state(dock_state)
            self.main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
            dock.sigClosed.connect(partial(self.on_dock_closed, name))
        self.update_closable()

    def first_log_dock(self):
        if self.docks:
            return None
        dock = self.create_new_dock(False)
        return dock


class LogWidgetHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.callback = None
        self.setFormatter(logging.Formatter("%(name)s:%(message)s"))

    def emit(self, record):
        if self.callback is not None:
            message = self.format(record)
            self.callback((record.levelno, record.source,
                           record.created, message))


def init_log(args, local_source):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)  # we use our custom filter only
    flt = SourceFilter(logging.INFO + args.quiet*10 - args.verbose*10,
                       local_source)
    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s:%(source)s:%(name)s:%(message)s"))
    handlers.append(console_handler)

    widget_handler = LogWidgetHandler()
    handlers.append(widget_handler)

    for handler in handlers:
        handler.addFilter(flt)
        root_logger.addHandler(handler)

    return widget_handler
