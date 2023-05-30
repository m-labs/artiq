import asyncio
import logging

import numpy as np
from PyQt5 import QtCore, QtWidgets
from sipyco import pyon

from artiq.tools import short_format, exc_to_warning
from artiq.gui.tools import LayoutWidget, QRecursiveFilterProxyModel
from artiq.gui.models import DictSyncTreeSepModel
from artiq.gui.scientific_spinbox import ScientificSpinBox


logger = logging.getLogger(__name__)


async def rename(key, new_key, value, persist, dataset_ctl):
    if key != new_key:
        await dataset_ctl.delete(key)
    await dataset_ctl.set(new_key, value, persist)


class CreateEditDialog(QtWidgets.QDialog):
    def __init__(self, parent, dataset_ctl, key=None, value=None, persist=False):
        QtWidgets.QDialog.__init__(self, parent=parent)
        self.dataset_ctl = dataset_ctl

        self.setWindowTitle("Create dataset" if key is None else "Edit dataset")
        grid = QtWidgets.QGridLayout()
        grid.setRowMinimumHeight(1, 40)
        grid.setColumnMinimumWidth(2, 60)
        self.setLayout(grid)

        grid.addWidget(QtWidgets.QLabel("Name:"), 0, 0)
        self.name_widget = QtWidgets.QLineEdit()
        grid.addWidget(self.name_widget, 0, 1)

        grid.addWidget(QtWidgets.QLabel("Value:"), 1, 0)
        self.value_widget = QtWidgets.QLineEdit()
        self.value_widget.setPlaceholderText('PYON (Python)')
        grid.addWidget(self.value_widget, 1, 1)
        self.data_type = QtWidgets.QLabel("data type")
        grid.addWidget(self.data_type, 1, 2)
        self.value_widget.textChanged.connect(self.dtype)

        grid.addWidget(QtWidgets.QLabel("Persist:"), 2, 0)
        self.box_widget = QtWidgets.QCheckBox()
        grid.addWidget(self.box_widget, 2, 1)

        self.ok = QtWidgets.QPushButton('&Ok')
        self.ok.setEnabled(False)
        self.cancel = QtWidgets.QPushButton('&Cancel')
        self.buttons = QtWidgets.QDialogButtonBox(self)
        self.buttons.addButton(
            self.ok, QtWidgets.QDialogButtonBox.AcceptRole)
        self.buttons.addButton(
            self.cancel, QtWidgets.QDialogButtonBox.RejectRole)
        grid.setRowStretch(3, 1)
        grid.addWidget(self.buttons, 4, 0, 1, 3, alignment=QtCore.Qt.AlignHCenter)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.key = key
        self.name_widget.setText(key)
        self.value_widget.setText(value)
        self.box_widget.setChecked(persist)

    def accept(self):
        key = self.name_widget.text()
        value = self.value_widget.text()
        persist = self.box_widget.isChecked()
        if self.key and self.key != key:
            asyncio.ensure_future(exc_to_warning(rename(self.key, key, pyon.decode(value), persist, self.dataset_ctl)))
        else:
            asyncio.ensure_future(exc_to_warning(self.dataset_ctl.set(key, pyon.decode(value), persist)))
        self.key = key
        QtWidgets.QDialog.accept(self)

    def dtype(self):
        txt = self.value_widget.text()
        try:
            result = pyon.decode(txt)
        except:
            pixmap = self.style().standardPixmap(
                QtWidgets.QStyle.SP_MessageBoxWarning)
            self.data_type.setPixmap(pixmap)
            self.ok.setEnabled(False)
        else:
            self.data_type.setText(type(result).__name__)
            self.ok.setEnabled(True)


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


class DatasetsDock(QtWidgets.QDockWidget):
    def __init__(self, dataset_sub, dataset_ctl):
        QtWidgets.QDockWidget.__init__(self, "Datasets")
        self.setObjectName("Datasets")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)
        self.dataset_ctl = dataset_ctl

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

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        create_action = QtWidgets.QAction("New dataset", self.table)
        create_action.triggered.connect(self.create_clicked)
        create_action.setShortcut("CTRL+N")
        create_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        self.table.addAction(create_action)
        edit_action = QtWidgets.QAction("Edit dataset", self.table)
        edit_action.triggered.connect(self.edit_clicked)
        edit_action.setShortcut("RETURN")
        edit_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        self.table.doubleClicked.connect(self.edit_clicked)
        self.table.addAction(edit_action)
        delete_action = QtWidgets.QAction("Delete dataset", self.table)
        delete_action.triggered.connect(self.delete_clicked)
        delete_action.setShortcut("DELETE")
        delete_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        self.table.addAction(delete_action)

        self.table_model = Model(dict())
        dataset_sub.add_setmodel_callback(self.set_model)

    def _search_datasets(self):
        if hasattr(self, "table_model_filter"):
            self.table_model_filter.setFilterFixedString(
                self.search.displayText())

    def set_model(self, model):
        self.table_model = model
        self.table_model_filter = QRecursiveFilterProxyModel()
        self.table_model_filter.setSourceModel(self.table_model)
        self.table.setModel(self.table_model_filter)

    def create_clicked(self):
        CreateEditDialog(self, self.dataset_ctl).open()

    def edit_clicked(self):
        idx = self.table.selectedIndexes()
        if idx:
            idx = self.table_model_filter.mapToSource(idx[0])
            key = self.table_model.index_to_key(idx)
            if key is not None:
                persist, value = self.table_model.backing_store[key]
                t = type(value)
                if np.issubdtype(t, np.number) or np.issubdtype(t, np.bool_):
                    value = str(value)
                elif np.issubdtype(t, np.unicode_):
                    value = '"{}"'.format(str(value))
                else:
                    value = pyon.encode(value)
                CreateEditDialog(self, self.dataset_ctl, key, value, persist).open()

    def delete_clicked(self):
        idx = self.table.selectedIndexes()
        if idx:
            idx = self.table_model_filter.mapToSource(idx[0])
            key = self.table_model.index_to_key(idx)
            if key is not None:
                asyncio.ensure_future(self.dataset_ctl.delete(key))

    def save_state(self):
        return bytes(self.table.header().saveState())

    def restore_state(self, state):
        self.table.header().restoreState(QtCore.QByteArray(state))
