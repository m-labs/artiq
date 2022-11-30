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
        self.widget = QtWidgets.QGroupBox()
        self.hbox = QtWidgets.QHBoxLayout()
        self.f_radio = QtWidgets.QRadioButton("false")
        self.t_radio = QtWidgets.QRadioButton("true")
        self.hbox.addWidget(self.f_radio)
        self.hbox.addWidget(self.t_radio)
        self.hbox.addStretch(1)
        self.widget.setLayout(self.hbox)
        self.f_radio.toggle()

    def get_value(self):
        return self.t_radio.isChecked()

    def set(self, val):
        if bool(val):
            self.t_radio.toggle()
        else:
            self.f_radio.toggle()

    def connect(self, f):
        self.f_radio.toggled.connect(f)
        self.t_radio.toggled.connect(f)


class NumberEditor:
    def __init__(self):
        self.widget = ScientificSpinBox()
        self.widget.setDecimals(13)
        self.widget.setPrecision()
        self.widget.setRelativeStep()
        self.widget.setValue(0)

    def set(self, val):
        try:
            self.widget.setValue(float(val))
        except (TypeError, ValueError):
            self.widget.setValue(0)

    def get_value(self):
        return self.widget.value()

    def connect(self, f):
        self.widget.valueChanged.connect(f)


class ComplexEditor:
    def __init__(self):
        self.widget = QtWidgets.QGroupBox()
        self.hbox = QtWidgets.QHBoxLayout()
        self.real = ScientificSpinBox()
        self.imag = ScientificSpinBox()
        self.hbox.addWidget(self.real)
        self.hbox.addWidget(QtWidgets.QLabel("+"))
        self.hbox.addWidget(self.imag)
        self.hbox.addWidget(QtWidgets.QLabel("j"))
        self.hbox.addStretch(1)
        self.widget.setLayout(self.hbox)

        self.real.setValue(0)
        self.imag.setValue(0)

        self.real.setDecimals(13)
        self.real.setPrecision()
        self.real.setRelativeStep()

        self.imag.setDecimals(13)
        self.imag.setPrecision()
        self.imag.setRelativeStep()

    def get_value(self):
        return complex(self.real.value(), self.imag.value())

    def set(self, val):
        try:
            value = complex(val)
        except (TypeError, ValueError):
            value = 0+0j
        self.real.setValue(value.real)
        self.imag.setValue(value.imag)

    def connect(self, f):
        self.real.valueChanged.connect(f)
        self.imag.valueChanged.connect(f)


class StrEditor(AutoEditor):
    def __init__(self):
        super().__init__()
        self.widget.setPlaceholderText("Text")

    def set(self, val):
        self.widget.setText(str(val))

    def get_value(self):
        return self.widget.text()


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

        self.editor_typemap = [
            ("auto", AutoEditor),
            ("None", NoneEditor),
            ("bool", BoolEditor),
            ("number", NumberEditor),
            ("complex", ComplexEditor),
            ("string", StrEditor),
        ]

        self.data_type_combo.addItems(map(lambda x: x[0], self.editor_typemap))
        self.editor_typemap = dict(self.editor_typemap)
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

        if not self.key:
            self.value_widget_holder = AutoEditor()
        else:
            typename = self.get_typename_for_value(self.value)
            self.value_widget_holder = self.editor_typemap[typename]()
            index = self.data_type_combo.findText(typename)
            if index != -1:
                self.data_type_combo.setCurrentIndex(index)
            self.value_widget_holder.set(self.value)

        self.grid.addWidget(self.value_widget_holder.widget, 1, 1)
        self.value_widget_holder.connect(self.dtype)
        self.dtype()

    @staticmethod
    def get_typename_for_value(value):
        t = type(value)
        if np.issubdtype(t, np.complex_):
            return "complex"
        elif np.issubdtype(t, np.number):
            return "number"
        elif np.issubdtype(t, np.bool_):
            return "bool"
        elif np.issubdtype(t, np.compat.unicode):
            return "string"
        elif value is None:
            return "None"
        return "auto"

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
