import asyncio

from quamash import QtGui
from pyqtgraph import dockarea

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import DictSyncModel


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
            return str(v)
        else:
           raise ValueError


class ParametersDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Parameters", size=(400, 300))

        self.table = QtGui.QTableView()
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.addWidget(self.table)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.subscriber = Subscriber("parameters", self.init_parameters_model)
        yield from self.subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.subscriber.close()

    def init_parameters_model(self, init):
        table_model = ParametersModel(self.table, init)
        self.table.setModel(table_model)
        return table_model
