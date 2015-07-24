import asyncio
from collections import OrderedDict
from functools import partial

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import DictSyncModel, short_format
from artiq.gui.displays import *


class ResultsModel(DictSyncModel):
    def __init__(self, parent, init):
        DictSyncModel.__init__(self, ["Result", "Value"],
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


class ResultsDock(dockarea.Dock):
    def __init__(self, dialog_parent, dock_area):
        dockarea.Dock.__init__(self, "Results", size=(1500, 500))
        self.dialog_parent = dialog_parent
        self.dock_area = dock_area

        grid = LayoutWidget()
        self.addWidget(grid)

        self.table = QtGui.QTableView()
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        grid.addWidget(self.table, 0, 0)

        add_display_box = QtGui.QGroupBox("Add display")
        grid.addWidget(add_display_box, 0, 1)
        display_grid = QtGui.QGridLayout()
        add_display_box.setLayout(display_grid)

        for n, name in enumerate(display_types.keys()):
            btn = QtGui.QPushButton(name)
            display_grid.addWidget(btn, n, 0)
            btn.clicked.connect(partial(self.create_dialog, name))

        self.displays = dict()

    def get_result(self, key):
        return self.table_model.backing_store[key]

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.subscriber = Subscriber("rt_results", self.init_results_model,
                                     self.on_mod)
        yield from self.subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.subscriber.close()

    def init_results_model(self, init):
        self.table_model = ResultsModel(self.table, init)
        self.table.setModel(self.table_model)
        return self.table_model

    def on_mod(self, mod):
        if mod["action"] == "init":
            for display in self.displays.values():
                display.update_data(self.table_model.backing_store)
            return

        if mod["action"] == "setitem":
            source = mod["key"]
        elif mod["path"]:
            source = mod["path"][0]
        else:
            return

        for display in self.displays.values():
            if source in display.data_sources():
                display.update_data(self.table_model.backing_store)

    def create_dialog(self, ty):
        dlg_class = display_types[ty][0]
        dlg = dlg_class(self.dialog_parent, None, dict(),
            sorted(self.table_model.backing_store.keys()),
            partial(self.create_display, ty, None))
        dlg.open()

    def create_display(self, ty, prev_name, name, settings):
        if prev_name is not None and prev_name in self.displays:
            raise NotImplementedError
        dsp_class = display_types[ty][1]
        dsp = dsp_class(name, settings)
        self.displays[name] = dsp
        dsp.update_data(self.table_model.backing_store)

        def on_close():
            del self.displays[name]
        dsp.sigClosed.connect(on_close)
        self.dock_area.addDock(dsp)
        self.dock_area.floatDock(dsp)
