import asyncio

from quamash import QtGui, QtCore
from pyqtgraph import dockarea

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import ListSyncModel


class _LogModel(ListSyncModel):
    def __init__(self, parent, init):
        ListSyncModel.__init__(self,
            ["RID", "Message"],
            parent, init)
        self.fixed_font = QtGui.QFont()
        self.fixed_font.setFamily("Monospace")

    def data(self, index, role):
        if (role == QtCore.Qt.FontRole and index.isValid()
                and index.column() == 1):
            return self.fixed_font
        else:
            return ListSyncModel.data(self, index, role)

    def convert(self, v, column):
        return v[column]


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

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.subscriber = Subscriber("log", self.init_log_model)
        yield from self.subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.subscriber.close()

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
