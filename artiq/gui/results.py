import asyncio
import logging
from functools import partial

from PyQt5 import QtCore, QtWidgets

from artiq.gui.tools import LayoutWidget


logger = logging.getLogger(__name__)


class ResultsDock(QtWidgets.QDockWidget):
    def __init__(self):
        QtWidgets.QDockWidget.__init__(self, "Results")
        self.setObjectName("Results")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        top_widget = LayoutWidget()
        self.setWidget(top_widget)

        self.stack = QtWidgets.QStackedWidget()
        top_widget.addWidget(self.stack, 1, 0, colspan=2)

        self.rt_buttons = LayoutWidget()
        self.rt_buttons.layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.rt_buttons)

        self.rt_model = QtWidgets.QFileSystemModel()
        self.rt_model.setRootPath(QtCore.QDir.currentPath())
        self.rt_model.setNameFilters(["HDF5 files (*.h5)"])
        self.rt_model.setNameFilterDisables(False)

        self.rt = QtWidgets.QTreeView()
        self.rt.setModel(self.rt_model)
        self.rt.setRootIndex(self.rt_model.index(QtCore.QDir.currentPath()))
        self.rt.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.rt.selectionModel().selectionChanged.connect(
            self.selection_changed)
        self.rt_buttons.addWidget(self.rt, 0, 0, colspan=2)

    def selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            print(self.rt_model.filePath(indexes[0]))

    def select(self, path):
        s = self.rt_model.index(path)
        self.rt.selectionModel().setCurrentIndex(
            s,
            QtCore.QItemSelectionModel.ClearAndSelect)
        self.rt.scrollTo(s)  # TODO: call_soon?

    def resultname_action(self, action):
        pass

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
