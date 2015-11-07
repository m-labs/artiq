import asyncio
from collections import OrderedDict
from functools import partial
import logging

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.tools import short_format
from artiq.gui.tools import DictSyncModel
from artiq.gui.displays import *

try:
    QSortFilterProxyModel = QtCore.QSortFilterProxyModel
except AttributeError:
    QSortFilterProxyModel = QtGui.QSortFilterProxyModel


logger = logging.getLogger(__name__)


class DatasetsModel(DictSyncModel):
    def __init__(self, parent, init):
        DictSyncModel.__init__(self, ["Dataset", "Persistent", "Value"],
                               parent, init)

    def sort_key(self, k, v):
        return k

    def convert(self, k, v, column):
        if column == 0:
            return k
        elif column == 1:
            return "Y" if v[0] else "N"
        elif column == 2:
            return short_format(v[1])
        else:
           raise ValueError


def _get_display_type_name(display_cls):
    for name, (_, cls) in display_types.items():
        if cls is display_cls:
            return name


class DatasetsDock(dockarea.Dock):
    def __init__(self, dialog_parent, dock_area):
        dockarea.Dock.__init__(self, "Datasets", size=(1500, 500))
        self.dialog_parent = dialog_parent
        self.dock_area = dock_area

        grid = LayoutWidget()
        self.addWidget(grid)

        self.search = QtGui.QLineEdit()
        self.search.setPlaceholderText("search...")
        self.search.editingFinished.connect(self._search_datasets)
        grid.addWidget(self.search, 0, 0)

        self.table = QtGui.QTableView()
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        grid.addWidget(self.table, 1, 0)

        add_display_box = QtGui.QGroupBox("Add display")
        grid.addWidget(add_display_box, 1, 1)
        display_grid = QtGui.QGridLayout()
        add_display_box.setLayout(display_grid)

        for n, name in enumerate(display_types.keys()):
            btn = QtGui.QPushButton(name)
            display_grid.addWidget(btn, n, 0)
            btn.clicked.connect(partial(self.create_dialog, name))

        self.displays = dict()

    def _search_datasets(self):
        self.table_model_filter.setFilterFixedString(self.search.displayText())

    def get_dataset(self, key):
        return self.table_model.backing_store[key][1]

    async def sub_connect(self, host, port):
        self.subscriber = Subscriber("datasets", self.init_datasets_model,
                                     self.on_mod)
        await self.subscriber.connect(host, port)

    async def sub_close(self):
        await self.subscriber.close()

    def init_datasets_model(self, init):
        self.table_model = DatasetsModel(self.table, init)
        self.table_model_filter = QSortFilterProxyModel()
        self.table_model_filter.setSourceModel(self.table_model)
        self.table.setModel(self.table_model_filter)
        return self.table_model

    def update_display_data(self, dsp):
        filtered_data = {k: self.table_model.backing_store[k][1]
                         for k in dsp.data_sources()
                         if k in self.table_model.backing_store}
        dsp.update_data(filtered_data)

    def on_mod(self, mod):
        if mod["action"] == "init":
            for display in self.displays.values():
                display.update_data(self.table_model.backing_store)
            return

        if mod["path"]:
            source = mod["path"][0]
        elif mod["action"] == "setitem":
            source = mod["key"]
        else:
            return

        for display in self.displays.values():
            if source in display.data_sources():
                self.update_display_data(display)

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
        self.update_display_data(dsp)

        def on_close():
            del self.displays[name]
        dsp.sigClosed.connect(on_close)
        self.dock_area.addDock(dsp)
        self.dock_area.floatDock(dsp)
        return dsp

    def save_state(self):
        r = dict()
        for name, display in self.displays.items():
            r[name] = {
                "ty": _get_display_type_name(type(display)),
                "settings": display.settings,
                "state": display.save_state()
            }
        return r

    def restore_state(self, state):
        for name, desc in state.items():
            try:
                dsp = self.create_display(desc["ty"], None, name,
                                          desc["settings"])
            except:
                logger.warning("Failed to create display '%s'", name,
                               exc_info=True)
            try:
                dsp.restore_state(desc["state"])
            except:
                logger.warning("Failed to restore display state of '%s'",
                               name, exc_info=True)
