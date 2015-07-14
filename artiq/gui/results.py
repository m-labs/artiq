import asyncio

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import DictSyncModel


def _fmt_type(v):
    t = type(v)
    r = t.__name__
    if t is list or t is dict or t is set:
        r += " ({})".format(len(v))
    return r


class ResultsModel(DictSyncModel):
    def __init__(self, parent, init):
        DictSyncModel.__init__(self, ["Result", "Type"],
                               parent, init)

    def sort_key(self, k, v):
        return k

    def convert(self, k, v, column):
        if column == 0:
            return k
        elif column == 1:
            return _fmt_type(v)
        else:
           raise ValueError


class ResultsDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Results", size=(1500, 500))

        grid = LayoutWidget()
        self.addWidget(grid)

        self.table = QtGui.QTableView()
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        grid.addWidget(self.table, 0, 0)

        add_display_box = QtGui.QGroupBox("Add display")
        grid.addWidget(add_display_box, 0, 1)
        display_grid = QtGui.QGridLayout()
        add_display_box.setLayout(display_grid)

        for n, name in enumerate(["Number", "XY", "Histogram"]):
            btn = QtGui.QPushButton(name)
            display_grid.addWidget(btn, n, 0)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.subscriber = Subscriber("rt_results", self.init_results_model)
        yield from self.subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.subscriber.close()

    def init_results_model(self, init):
        table_model = ResultsModel(self.table, init)
        self.table.setModel(table_model)
        return table_model
