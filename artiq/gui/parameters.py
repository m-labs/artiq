import asyncio

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import DictSyncModel, short_format


class ParametersModel(DictSyncModel):
    def __init__(self, parent, init):
        DictSyncModel.__init__(self, ["Parameter", "Value"],
                               parent, init)

    def sort_key(self, k, v):
        return k

    def convert(self, k, v, column):
        if column == 0:
            return k
        elif column == 1:
            return short_format(v)
        else:
           raise ValueError


class ParametersDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Parameters", size=(400, 300))

        grid = LayoutWidget()
        self.addWidget(grid)

        self.search = QtGui.QLineEdit()
        self.search.setPlaceholderText("search...")
        self.search.editingFinished.connect(self._search_parameters)
        grid.addWidget(self.search, 0, 0)

        self.table = QtGui.QTableView()
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        grid.addWidget(self.table, 1, 0)

    def get_parameter(self, key):
        return self.table_model.backing_store[key]

    def _search_parameters(self):
        model = self.table.model()
        parentIndex = model.index(0, 0)
        numRows = model.rowCount(parentIndex)

        for row in range(numRows):
            index = model.index(row, 0)
            parameter = model.data(index, QtCore.Qt.DisplayRole)
            if parameter.startswith(self.search.displayText()):
                self.table.showRow(row)
            else:
                self.table.hideRow(row)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.subscriber = Subscriber("parameters", self.init_parameters_model)
        yield from self.subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.subscriber.close()

    def init_parameters_model(self, init):
        self.table_model = ParametersModel(self.table, init)
        self.table.setModel(self.table_model)
        return self.table_model
