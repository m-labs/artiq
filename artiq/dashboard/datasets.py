import asyncio
import logging

import numpy as np
from PyQt5 import QtCore, QtWidgets
from sipyco import pyon

from artiq.tools import scale_from_metadata, short_format, exc_to_warning
from artiq.gui.tools import LayoutWidget, QRecursiveFilterProxyModel
from artiq.gui.models import DictSyncTreeSepModel


logger = logging.getLogger(__name__)


async def rename(key, new_key, value, metadata, persist, dataset_ctl):
    if key != new_key:
        await dataset_ctl.delete(key)
    await dataset_ctl.set(new_key, value, metadata=metadata, persist=persist)


class CreateEditDialog(QtWidgets.QDialog):
    def __init__(self, parent, dataset_ctl, key=None, value=None, metadata=None, persist=False):
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

        grid.addWidget(QtWidgets.QLabel("Unit:"), 2, 0)
        self.unit_widget = QtWidgets.QLineEdit()
        grid.addWidget(self.unit_widget, 2, 1)

        grid.addWidget(QtWidgets.QLabel("Scale:"), 3, 0)
        self.scale_widget = QtWidgets.QLineEdit()
        grid.addWidget(self.scale_widget, 3, 1)

        grid.addWidget(QtWidgets.QLabel("Precision:"), 4, 0)
        self.precision_widget = QtWidgets.QLineEdit()
        grid.addWidget(self.precision_widget, 4, 1)

        grid.addWidget(QtWidgets.QLabel("Persist:"), 5, 0)
        self.box_widget = QtWidgets.QCheckBox()
        grid.addWidget(self.box_widget, 5, 1)

        self.ok = QtWidgets.QPushButton('&Ok')
        self.ok.setEnabled(False)
        self.cancel = QtWidgets.QPushButton('&Cancel')
        self.buttons = QtWidgets.QDialogButtonBox(self)
        self.buttons.addButton(
            self.ok, QtWidgets.QDialogButtonBox.AcceptRole)
        self.buttons.addButton(
            self.cancel, QtWidgets.QDialogButtonBox.RejectRole)
        grid.setRowStretch(6, 1)
        grid.addWidget(self.buttons, 7, 0, 1, 3, alignment=QtCore.Qt.AlignHCenter)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.key = key
        self.name_widget.setText(key)

        value_edit_string = self.value_to_edit_string(value)
        if metadata is not None:
            scale = scale_from_metadata(metadata)
            t = value.dtype if value is np.ndarray else type(value)
            if scale != 1 and np.issubdtype(t, np.number):
                # degenerates to float type
                value_edit_string = self.value_to_edit_string(value / scale)
            self.unit_widget.setText(metadata.get('unit', ''))
            self.scale_widget.setText(str(metadata.get('scale', '')))
            self.precision_widget.setText(str(metadata.get('precision', '')))

        self.value_widget.setText(value_edit_string)
        self.box_widget.setChecked(persist)

    def accept(self):
        key = self.name_widget.text()
        value = self.value_widget.text()
        persist = self.box_widget.isChecked()
        unit = self.unit_widget.text()
        scale = self.scale_widget.text()
        precision = self.precision_widget.text()
        metadata = {}
        if unit != "":
            metadata['unit'] = unit
        if scale != "":
            metadata['scale'] = float(scale)
        if precision != "":
            metadata['precision'] = int(precision)
        scale = scale_from_metadata(metadata)
        value = self.parse_edit_string(value)
        t = value.dtype if value is np.ndarray else type(value)
        if scale != 1 and np.issubdtype(t, np.number):
            # degenerates to float type
            value = float(value * scale)
        if self.key and self.key != key:
            asyncio.ensure_future(exc_to_warning(rename(self.key, key, value, metadata, persist,
                                                        self.dataset_ctl)))
        else:
            asyncio.ensure_future(exc_to_warning(self.dataset_ctl.set(key, value, metadata=metadata,
                                                                      persist=persist)))
        self.key = key
        QtWidgets.QDialog.accept(self)

    def dtype(self):
        txt = self.value_widget.text()
        try:
            result = self.parse_edit_string(txt)
            # ensure only pyon compatible types are permissable
            pyon.encode(result)
        except:
            pixmap = self.style().standardPixmap(
                QtWidgets.QStyle.SP_MessageBoxWarning)
            self.data_type.setPixmap(pixmap)
            self.ok.setEnabled(False)
        else:
            self.data_type.setText(type(result).__name__)
            self.ok.setEnabled(True)

    @staticmethod
    def parse_edit_string(s):
        if s == "":
            raise TypeError
        _eval_dict = {
            "__builtins__": {},
            "array": np.array,
            "null": np.nan,
            "inf": np.inf
        }
        for t_ in pyon._numpy_scalar:
            _eval_dict[t_] = eval("np.{}".format(t_), {"np": np})
        return eval(s, _eval_dict, {})

    @staticmethod
    def value_to_edit_string(v):
        t = type(v)
        r = ""
        if isinstance(v, np.generic):
            r += t.__name__
            r += "("
            r += repr(v)
            r += ")"
        elif v is None:
            return r
        else:
            r += repr(v)
        return r


class Model(DictSyncTreeSepModel):
    def __init__(self, init):
        DictSyncTreeSepModel.__init__(self, ".",
                                      ["Dataset", "Persistent", "Value"],
                                      init)

    def convert(self, k, v, column):
        if column == 1:
            return "Y" if v[0] else "N"
        elif column == 2:
            return short_format(v[1], v[2])
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
                persist, value, metadata = self.table_model.backing_store[key]
                CreateEditDialog(self, self.dataset_ctl, key, value, metadata, persist).open()

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
