import asyncio
import logging
import ast

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


class AutoEditor:
    def __init__(self):
        self.widget = QtWidgets.QLineEdit()
        self.widget.setPlaceholderText('PYON (Python)')

    def get_value(self):
        return pyon.decode(self.widget.text())

    def set(self, val):
        self.widget.setText(pyon.encode(val))

    def connect(self, f):
        self.widget.textChanged.connect(f)


class NoneEditor:
    def __init__(self):
        self.widget = QtWidgets.QLabel("None")

    def get_value(self):
        return None

    def connect(self, f):
        pass

    def set(self, val):
        pass


class BoolEditor:
    def __init__(self):
        self.widget = QtWidgets.QCheckBox()
        self.widget.setChecked(False)

    def get_value(self):
        return self.widget.isChecked()

    def set(self, val):
        if type(val) is str and val.lower() == "false":
            val = False
        self.widget.setChecked(bool(val))

    def connect(self, f):
        self.widget.stateChanged.connect(f)


class IntEditor(AutoEditor):
    def __init__(self):
        super().__init__()
        self.widget.setPlaceholderText("Integer number")
        self.converter = int

    def set(self, val):
        # first, try use python format
        try:
            self.widget.setText(str(self.converter(val)))
        except (TypeError, ValueError):  # fallback to plaintext
            self.widget.setText(str(val))

    def get_value(self):
        return self.converter(self.widget.text())


class FloatEditor(IntEditor):
    def __init__(self):
        super().__init__()
        self.widget.setPlaceholderText("Float number")
        self.converter = float


class ComplexEditor(IntEditor):
    def __init__(self):
        super().__init__()
        self.widget.setPlaceholderText("Complex number")
        self.converter = complex


class StrEditor(AutoEditor):
    def __init__(self):
        super().__init__()
        self.widget.setPlaceholderText("Text")

    def set(self, val):
        self.widget.setText(str(val))

    def get_value(self):
        return self.widget.text()


class TupleEditor(AutoEditor):
    def __init__(self):
        super().__init__()
        self.widget.setPlaceholderText("Comma-separated values")

    @staticmethod
    def remove_brackets(value):
        if value[0] in {"(", "{", "["}:
            value = value[1:]
        if value[-1] in {")", "}", "]"}:
            value = value[:-1]
        return value

    def set(self, val):
        self.widget.setText(self.remove_brackets(str(val)))

    def get_value(self):
        return tuple(ast.literal_eval("[{}]".format(self.widget.text())))


class ListEditor(TupleEditor):
    def get_value(self):
        return list(super().get_value())


class SetEditor(TupleEditor):
    def get_value(self):
        return set(super().get_value())


class DictEditor(SetEditor):
    def get_value(self):
        return dict(ast.literal_eval("{{ {} }}".format(self.widget.text())))


class CreateEditDialog(QtWidgets.QDialog):
    def __init__(self, parent, dataset_ctl, key=None, value=None, persist=False):
        QtWidgets.QDialog.__init__(self, parent=parent)
        self.dataset_ctl = dataset_ctl

        self.setWindowTitle("Create dataset" if key is None else "Edit dataset")
        self.grid = QtWidgets.QGridLayout()
        self.grid.setRowMinimumHeight(1, 40)
        self.grid.setColumnMinimumWidth(2, 60)
        self.setLayout(self.grid)

        self.grid.addWidget(QtWidgets.QLabel("Name:"), 0, 0)
        self.name_widget = QtWidgets.QLineEdit()
        self.grid.addWidget(self.name_widget, 0, 1)

        self.grid.addWidget(QtWidgets.QLabel("Value:"), 1, 0)

        self.data_type_combo = QtWidgets.QComboBox(self)
        self.grid.addWidget(self.data_type_combo, 1, 2)

        self.editor_typemap = {
            "auto": AutoEditor,
            "NoneType": NoneEditor,
            "bool": BoolEditor,
            "int": IntEditor,
            "float": FloatEditor,
            "complex": ComplexEditor,
            "str": StrEditor,
            "tuple": TupleEditor,
            "list": ListEditor,
            "dict": DictEditor,
            "set": SetEditor,
        }

        self.data_type_combo.addItems(sorted(self.editor_typemap.keys(), key=lambda x: x.lower()))
        width = self.data_type_combo.minimumSizeHint().width()
        self.data_type_combo.view().setMinimumWidth(width)
        self.data_type_combo.currentIndexChanged.connect(self.update_input_field)

        self.data_type_ind = QtWidgets.QLabel("")
        self.grid.addWidget(self.data_type_ind, 1, 3)
        self.data_type_ind.setFixedWidth(35)

        self.data_type = QtWidgets.QLabel("")
        self.grid.addWidget(self.data_type, 2, 2)
        self.data_type.setFixedWidth(100)

        self.grid.addWidget(QtWidgets.QLabel("Persist:"), 2, 0)
        self.box_widget = QtWidgets.QCheckBox()
        self.grid.addWidget(self.box_widget, 2, 1)

        self.ok = QtWidgets.QPushButton('&Ok')
        self.ok.setEnabled(False)
        self.cancel = QtWidgets.QPushButton('&Cancel')
        self.buttons = QtWidgets.QDialogButtonBox(self)
        self.buttons.addButton(
            self.ok, QtWidgets.QDialogButtonBox.AcceptRole)
        self.buttons.addButton(
            self.cancel, QtWidgets.QDialogButtonBox.RejectRole)

        self.grid.addWidget(self.buttons, 4, 0, 1, 4, alignment=QtCore.Qt.AlignHCenter)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.key = key
        self.value = value
        self.name_widget.setText(key)
        self.box_widget.setChecked(persist)

        if not self.key or type(self.value).__name__ not in self.editor_typemap:
            self.value_widget_holder = AutoEditor()
        else:
            self.value_widget_holder = self.editor_typemap[type(self.value).__name__]()
            index = self.data_type_combo.findText(type(self.value).__name__)
            if index != -1:
                self.data_type_combo.setCurrentIndex(index)
        if self.key:
            self.value_widget_holder.set(self.value)

        self.grid.addWidget(self.value_widget_holder.widget, 1, 1)
        self.value_widget_holder.connect(self.dtype)
        self.dtype()

    def update_input_field(self):
        new_widget_name = self.data_type_combo.currentText()
        if type(self.value_widget_holder) is self.editor_typemap[new_widget_name]:
            return
        new_widget = self.editor_typemap[new_widget_name]()
        self.grid.replaceWidget(self.value_widget_holder.widget, new_widget.widget)
        self.value_widget_holder.widget.deleteLater()
        self.value_widget_holder = new_widget
        if self.key:
            self.value_widget_holder.set(self.value)

        self.value_widget_holder.connect(self.dtype)
        self.dtype()

    def accept(self):
        key = self.name_widget.text()
        value = self.value_widget_holder.get_value()
        persist = self.box_widget.isChecked()
        if self.key and self.key != key:
            asyncio.ensure_future(exc_to_warning(rename(self.key, key, value, persist, self.dataset_ctl)))
        else:
            asyncio.ensure_future(exc_to_warning(self.dataset_ctl.set(key, value, persist)))
        self.key = key
        QtWidgets.QDialog.accept(self)

    def dtype(self):
        result = ""
        try:
            self.value = self.value_widget_holder.get_value()
            result = type(self.value).__name__
        except:
            pixmap = self.style().standardPixmap(QtWidgets.QStyle.SP_MessageBoxWarning)
            self.data_type_ind.setPixmap(pixmap)
            self.ok.setEnabled(False)
        else:
            pixmap = self.style().standardPixmap(QtWidgets.QStyle.SP_DialogApplyButton)
            self.data_type_ind.setPixmap(pixmap)
            self.ok.setEnabled(True)
        finally:
            if self.data_type_combo.currentText() == "auto":
                self.data_type.setText(result)
            else:
                self.data_type.setText("")


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
    def __init__(self, datasets_sub, dataset_ctl):
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
        datasets_sub.add_setmodel_callback(self.set_model)

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
