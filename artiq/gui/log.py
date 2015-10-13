import asyncio
import logging
import time

from quamash import QtGui, QtCore
from pyqtgraph import dockarea

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import ListSyncModel


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
                return ListSyncModel.data(self, index, role)
        elif role == QtCore.Qt.ForegroundRole and index.isValid():
            level = self.backing_store[index.row()][0]
            if level <= logging.DEBUG:
                return self.debug_fg
            else:
                return ListSyncModel.data(self, index, role)
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


class LogDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Log", size=(1000, 300))

        self.log = QtGui.QTableView()
        self.log.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.log.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.log.setHorizontalScrollMode(
            QtGui.QAbstractItemView.ScrollPerPixel)
        self.log.setShowGrid(False)
        self.log.setTextElideMode(QtCore.Qt.ElideNone)
        self.addWidget(self.log)
        self.scroll_at_bottom = False

    async def sub_connect(self, host, port):
        self.subscriber = Subscriber("log", self.init_log_model)
        await self.subscriber.connect(host, port)

    async def sub_close(self):
        await self.subscriber.close()

    def rows_inserted_before(self):
        scrollbar = self.log.verticalScrollBar()
        self.scroll_at_bottom = scrollbar.value() == scrollbar.maximum()

    def rows_inserted_after(self):
        if self.scroll_at_bottom:
            self.log.scrollToBottom()

    def init_log_model(self, init):
        table_model = _LogModel(self.log, init)
        self.log.setModel(table_model)
        table_model.rowsAboutToBeInserted.connect(self.rows_inserted_before)
        table_model.rowsInserted.connect(self.rows_inserted_after)
        return table_model
