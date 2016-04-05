from PyQt5 import QtCore, QtWidgets

from artiq.tools import short_format
from artiq.gui.tools import LayoutWidget
from artiq.gui.models import DictSyncTreeSepModel

# reduced read-only version of artiq.gui.datasets


class Model(DictSyncTreeSepModel):
    def __init__(self,  init):
        DictSyncTreeSepModel.__init__(self, ".", ["Dataset", "Value"], init)

    def convert(self, k, v, column):
        return short_format(v[1])


class DatasetsDock(QtWidgets.QDockWidget):
    def __init__(self, datasets_sub):
        QtWidgets.QDockWidget.__init__(self, "Datasets")
        self.setObjectName("Datasets")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        grid = LayoutWidget()
        self.setWidget(grid)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("search...")
        self.search.editingFinished.connect(self._search_datasets)
        grid.addWidget(self.search, 0, 0)

        self.table = QtWidgets.QTreeView()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        grid.addWidget(self.table, 1, 0)

        self.table_model = Model(dict())
        datasets_sub.add_setmodel_callback(self.set_model)

    def _search_datasets(self):
        if hasattr(self, "table_model_filter"):
            self.table_model_filter.setFilterFixedString(
                self.search.displayText())

    def set_model(self, model):
        self.table_model = model
        self.table_model_filter = QtCore.QSortFilterProxyModel()
        self.table_model_filter.setSourceModel(self.table_model)
        self.table.setModel(self.table_model_filter)

    def save_state(self):
        return bytes(self.table.header().saveState())

    def restore_state(self, state):
        self.table.header().restoreState(QtCore.QByteArray(state))
