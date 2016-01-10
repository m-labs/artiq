import asyncio
from collections import OrderedDict
from functools import partial
import logging

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.tools import short_format
from artiq.gui.models import DictSyncTreeSepModel

try:
    QSortFilterProxyModel = QtCore.QSortFilterProxyModel
except AttributeError:
    QSortFilterProxyModel = QtGui.QSortFilterProxyModel


logger = logging.getLogger(__name__)


class Model(DictSyncTreeSepModel):
    def __init__(self,  init):
        DictSyncTreeSepModel.__init__(self, ".",
            ["Dataset", "Persistent", "Value"],
            init)

    def convert(self, k, v, column):
        if column == 1:
            return "Y" if v[0] else "N"
        elif column == 2:
            return short_format(v[1])
        else:
           raise ValueError


class DatasetsDock(dockarea.Dock):
    def __init__(self, dialog_parent, dock_area, datasets_sub):
        dockarea.Dock.__init__(self, "Datasets")
        self.dialog_parent = dialog_parent
        self.dock_area = dock_area

        grid = LayoutWidget()
        self.addWidget(grid)

        self.search = QtGui.QLineEdit()
        self.search.setPlaceholderText("search...")
        self.search.editingFinished.connect(self._search_datasets)
        grid.addWidget(self.search, 0, 0)

        self.table = QtGui.QTreeView()
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.header().setResizeMode(QtGui.QHeaderView.ResizeToContents)
        grid.addWidget(self.table, 1, 0)

        self.table_model = Model(dict())
        datasets_sub.add_setmodel_callback(self.set_model)

    def _search_datasets(self):
        if hasattr(self, "table_model_filter"):
            self.table_model_filter.setFilterFixedString(
                self.search.displayText())

    def set_model(self, model):
        self.table_model = model
        self.table_model_filter = QSortFilterProxyModel()
        self.table_model_filter.setSourceModel(self.table_model)
        self.table.setModel(self.table_model_filter)
