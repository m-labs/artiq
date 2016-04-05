import logging

import h5py
from PyQt5 import QtCore, QtWidgets

from artiq.gui.tools import LayoutWidget

logger = logging.getLogger(__name__)


class ResultsDock(QtWidgets.QDockWidget):
    def __init__(self, datasets):
        QtWidgets.QDockWidget.__init__(self, "Results")

        self.datasets = datasets

        self.setObjectName("Results")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        top_widget = LayoutWidget()
        self.setWidget(top_widget)

        self.rt_model = QtWidgets.QFileSystemModel()
        self.rt_model.setRootPath(QtCore.QDir.currentPath())
        self.rt_model.setNameFilters(["*.h5"])
        self.rt_model.setNameFilterDisables(False)

        self.rt = QtWidgets.QTreeView()
        self.rt.setModel(self.rt_model)
        self.rt.setRootIndex(self.rt_model.index(QtCore.QDir.currentPath()))
        self.rt.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rt.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        top_widget.addWidget(self.rt, 0, 0)

        self.rl = QtWidgets.QListView()
        self.rl.setModel(self.rt_model)
        self.rl.setRootIndex(self.rt_model.index(QtCore.QDir.currentPath()))
        self.rl.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rl.selectionModel().selectionChanged.connect(
            self.selection_changed)
        top_widget.addWidget(self.rl, 0, 1)

    def selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            return
        path = self.rt_model.filePath(indexes[0])
        logger.info("opening %s", path)
        try:
            with h5py.File(path, "r") as f:
                rd = {}
                for k in f["datasets"]:
                    rd[k] = False, f[k].value
                self.datasets.init(rd)
        except:
            pass

    def select(self, path):
        s = self.rt_model.index(path)
        self.rt.selectionModel().setCurrentIndex(
            s,
            QtCore.QItemSelectionModel.ClearAndSelect)
        self.rt.scrollTo(s)  # TODO: call_soon?

    def save_state(self):
        return {
            "selected": self.rt_model.filePath(
                self.rt.selectionModel().currentIndex()),
            "header": bytes(self.rt.header().saveState()),
        }

    def restore_state(self, state):
        selected = state.get("selected")
        if selected:
            self.select(selected)
        header = state.get("header")
        if header:
            self.rt.header().restoreState(QtCore.QByteArray(header))
