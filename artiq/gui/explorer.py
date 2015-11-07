import asyncio
import logging

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.protocols import pyon
from artiq.gui.tools import DictSyncModel
from artiq.gui.scan import ScanController
from artiq.gui.shortcuts import ShortcutManager


class _ExplistModel(DictSyncModel):
    def __init__(self, explorer, parent, init):
        self.explorer = explorer
        DictSyncModel.__init__(self,
            ["Experiment"],
            parent, init)

    def sort_key(self, k, v):
        return k

    def convert(self, k, v, column):
        return k

    def __setitem__(self, k, v):
        DictSyncModel.__setitem__(self, k, v)
        if k == self.explorer.selected_key:
            self.explorer.update_selection(k, k)


class _FreeValueEntry(QtGui.QLineEdit):
    def __init__(self, procdesc):
        QtGui.QLineEdit.__init__(self)
        if "default" in procdesc:
            self.set_argument_value(procdesc["default"])

    def get_argument_value(self):
        return pyon.decode(self.text())

    def set_argument_value(self, value):
        self.setText(pyon.encode(value))


class _BooleanEntry(QtGui.QCheckBox):
    def __init__(self, procdesc):
        QtGui.QCheckBox.__init__(self)
        if "default" in procdesc:
            self.set_argument_value(procdesc["default"])

    def get_argument_value(self):
        return self.isChecked()

    def set_argument_value(self, value):
        self.setChecked(value)


class _EnumerationEntry(QtGui.QComboBox):
    def __init__(self, procdesc):
        QtGui.QComboBox.__init__(self)
        self.choices = procdesc["choices"]
        self.addItems(self.choices)
        if "default" in procdesc:
            self.set_argument_value(procdesc["default"])

    def get_argument_value(self):
        return self.choices[self.currentIndex()]

    def set_argument_value(self, value):
        idx = self.choices.index(value)
        self.setCurrentIndex(idx)


class _NumberEntry(QtGui.QDoubleSpinBox):
    def __init__(self, procdesc):
        QtGui.QDoubleSpinBox.__init__(self)
        self.scale = procdesc["scale"]
        self.setDecimals(procdesc["ndecimals"])
        self.setSingleStep(procdesc["step"]/self.scale)
        if procdesc["min"] is not None:
            self.setMinimum(procdesc["min"]/self.scale)
        else:
            self.setMinimum(float("-inf"))
        if procdesc["max"] is not None:
            self.setMaximum(procdesc["max"]/self.scale)
        else:
            self.setMaximum(float("inf"))
        if procdesc["unit"]:
            self.setSuffix(" " + procdesc["unit"])
        if "default" in procdesc:
            self.set_argument_value(procdesc["default"])

    def get_argument_value(self):
        return self.value()*self.scale

    def set_argument_value(self, value):
        self.setValue(value/self.scale)


class _StringEntry(QtGui.QLineEdit):
    def __init__(self, procdesc):
        QtGui.QLineEdit.__init__(self)
        if "default" in procdesc:
            self.set_argument_value(procdesc["default"])

    def get_argument_value(self):
        return self.text()

    def set_argument_value(self, value):
        self.setText(value)


_procty_to_entry = {
    "FreeValue": _FreeValueEntry,
    "BooleanValue": _BooleanEntry,
    "EnumerationValue": _EnumerationEntry,
    "NumberValue": _NumberEntry,
    "StringValue": _StringEntry,
    "Scannable": ScanController
}


class _ArgumentEditor(QtGui.QTreeWidget):
    def __init__(self, main_window):
        QtGui.QTreeWidget.__init__(self)
        self.setColumnCount(2)
        self.header().setResizeMode(QtGui.QHeaderView.ResizeToContents)
        self.header().setVisible(False)
        self.setSelectionMode(QtGui.QAbstractItemView.NoSelection)

        self.main_window = main_window
        self._groups = dict()
        self.set_arguments([])

    def clear(self):
        QtGui.QTreeWidget.clear(self)
        self._groups.clear()

    def _get_group(self, name):
        if name in self._groups:
            return self._groups[name]
        group = QtGui.QTreeWidgetItem([name, ""])
        for c in 0, 1:
            group.setBackground(c, QtGui.QBrush(QtGui.QColor(100, 100, 100)))
            group.setForeground(c, QtGui.QBrush(QtGui.QColor(220, 220, 255)))
            font = group.font(c)
            font.setBold(True)
            group.setFont(c, font)
        self.addTopLevelItem(group)
        self._groups[name] = group
        return group

    def set_arguments(self, arguments):
        self.clear()

        if not arguments:
            self.addTopLevelItem(QtGui.QTreeWidgetItem(["No arguments", ""]))

        self._args_to_entries = dict()
        for n, (name, (procdesc, group)) in enumerate(arguments):
            entry = _procty_to_entry[procdesc["ty"]](procdesc)
            self._args_to_entries[name] = entry

            widget_item = QtGui.QTreeWidgetItem([name, ""])
            if group is None:
                self.addTopLevelItem(widget_item)
            else:
                self._get_group(group).addChild(widget_item)
            self.setItemWidget(widget_item, 1, entry)

    def get_argument_values(self, show_error_message):
        r = dict()
        for arg, entry in self._args_to_entries.items():
            try:
                r[arg] = entry.get_argument_value()
            except Exception as e:
                if show_error_message:
                    msgbox = QtGui.QMessageBox(self.main_window)
                    msgbox.setWindowTitle("Error")
                    msgbox.setText("Failed to obtain value for argument '{}':\n{}"
                                   .format(arg, str(e)))
                    msgbox.setStandardButtons(QtGui.QMessageBox.Ok)
                    msgbox.show()
                return None
        return r

    def set_argument_values(self, arguments, ignore_errors):
        for arg, value in arguments.items():
            try:
                entry = self._args_to_entries[arg]
                entry.set_argument_value(value)
            except:
                if not ignore_errors:
                    raise

    def save_state(self):
        expanded = []
        for k, v in self._groups.items():
            if v.isExpanded():
                expanded.append(k)
        argument_values = self.get_argument_values(False)
        return {
            "expanded": expanded,
            "argument_values": argument_values
        }

    def restore_state(self, state):
        self.set_argument_values(state["argument_values"], True)
        for e in state["expanded"]:
            try:
                self._groups[e].setExpanded(True)
            except KeyError:
                pass


class ExplorerDock(dockarea.Dock):
    def __init__(self, main_window, status_bar, schedule_ctl):
        dockarea.Dock.__init__(self, "Explorer", size=(1500, 500))

        self.main_window = main_window
        self.status_bar = status_bar
        self.schedule_ctl = schedule_ctl

        self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.addWidget(self.splitter)

        grid = LayoutWidget()
        self.splitter.addWidget(grid)

        self.el = QtGui.QListView()
        self.el.selectionChanged = self._selection_changed
        self.selected_key = None
        grid.addWidget(self.el, 0, 0, colspan=4)

        self.datetime = QtGui.QDateTimeEdit()
        self.datetime.setDisplayFormat("MMM d yyyy hh:mm:ss")
        self.datetime.setDate(QtCore.QDate.currentDate())
        self.datetime.dateTimeChanged.connect(self.enable_duedate)
        self.datetime_en = QtGui.QCheckBox("Due date:")
        grid.addWidget(self.datetime_en, 1, 0, colspan=2)
        grid.addWidget(self.datetime, 1, 2, colspan=2)

        self.pipeline = QtGui.QLineEdit()
        self.pipeline.setText("main")
        grid.addWidget(QtGui.QLabel("Pipeline:"), 2, 0, colspan=2)
        grid.addWidget(self.pipeline, 2, 2, colspan=2)

        self.priority = QtGui.QSpinBox()
        self.priority.setRange(-99, 99)
        grid.addWidget(QtGui.QLabel("Priority:"), 3, 0)
        grid.addWidget(self.priority, 3, 1)

        self.flush = QtGui.QCheckBox("Flush")
        self.flush.setToolTip("Flush the pipeline before starting the experiment")
        grid.addWidget(self.flush, 3, 2)

        self.log_level = QtGui.QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.setCurrentIndex(1)
        self.log_level.setToolTip("Minimum level for log entry production")
        grid.addWidget(self.log_level, 3, 3)

        submit = QtGui.QPushButton("Submit")
        submit.setShortcut("CTRL+RETURN")
        submit.setToolTip("Schedule the selected experiment (CTRL+ENTER)")
        grid.addWidget(submit, 4, 0, colspan=4)
        submit.clicked.connect(self.submit_clicked)

        self.argeditor = _ArgumentEditor(self.main_window)
        self.splitter.addWidget(self.argeditor)
        self.splitter.setSizes([grid.minimumSizeHint().width(), 1000])
        self.argeditor_states = dict()

        self.shortcuts = ShortcutManager(self.main_window, self)

        self.el.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        edit_shortcuts_action = QtGui.QAction("Edit shortcuts", self.el)
        edit_shortcuts_action.triggered.connect(self.edit_shortcuts)
        self.el.addAction(edit_shortcuts_action)

    def update_selection(self, selected, deselected):
        if deselected:
            self.argeditor_states[deselected] = self.argeditor.save_state()

        if selected:
            expinfo = self.explist_model.backing_store[selected]
            self.argeditor.set_arguments(expinfo["arguments"])
            if selected in self.argeditor_states:
                self.argeditor.restore_state(self.argeditor_states[selected])
            self.splitter.insertWidget(1, self.argeditor)
        self.selected_key = selected

    def _sel_to_key(self, selection):
        selection = selection.indexes()
        if selection:
            row = selection[0].row()
            return self.explist_model.row_to_key[row]
        else:
            return None

    def _selection_changed(self, selected, deselected):
        self.update_selection(self._sel_to_key(selected),
                              self._sel_to_key(deselected))

    def save_state(self):
        idx = self.el.selectedIndexes()
        if idx:
            row = idx[0].row()
            key = self.explist_model.row_to_key[row]
            self.argeditor_states[key] = self.argeditor.save_state()
        return {
            "argeditor": self.argeditor_states,
            "shortcuts": self.shortcuts.save_state()
        }

    def restore_state(self, state):
        try:
            argeditor_states = state["argeditor"]
            shortcuts_state = state["shortcuts"]
        except KeyError:
            return
        self.argeditor_states = argeditor_states
        self.shortcuts.restore_state(shortcuts_state)

    def enable_duedate(self):
        self.datetime_en.setChecked(True)

    async def sub_connect(self, host, port):
        self.explist_subscriber = Subscriber("explist",
                                             self.init_explist_model)
        await self.explist_subscriber.connect(host, port)

    async def sub_close(self):
        await self.explist_subscriber.close()

    def init_explist_model(self, init):
        self.explist_model = _ExplistModel(self, self.el, init)
        self.el.setModel(self.explist_model)
        return self.explist_model

    async def submit_task(self, pipeline_name, file, class_name, arguments,
                          priority, due_date, flush):
        expid = {
            "log_level": getattr(logging, self.log_level.currentText()),
            "repo_rev": None,
            "file": file,
            "class_name": class_name,
            "arguments": arguments,
        }
        rid = await self.schedule_ctl.submit(pipeline_name, expid,
                                             priority, due_date, flush)
        self.status_bar.showMessage("Submitted RID {}".format(rid))

    def submit(self, pipeline, key, priority, due_date, flush):
        # TODO: refactor explorer and cleanup.
        # Argument editors should immediately modify the global state.
        expinfo = self.explist_model.backing_store[key]
        if key == self.selected_key:
            arguments = self.argeditor.get_argument_values(True)
            if arguments is None:
                # There has been an error. Displaying the error message box
                # was done by argeditor.
                return
        else:
            try:
                arguments = self.argeditor_states[key]["argument_values"]
            except KeyError:
                arguments = dict()
        asyncio.ensure_future(self.submit_task(pipeline, expinfo["file"],
                                               expinfo["class_name"],
                                               arguments, priority, due_date,
                                               flush))

    def submit_clicked(self):
        if self.selected_key is not None:
            if self.datetime_en.isChecked():
                due_date = self.datetime.dateTime().toMSecsSinceEpoch()/1000
            else:
                due_date = None
            self.submit(self.pipeline.text(),
                        self.selected_key,
                        self.priority.value(),
                        due_date,
                        self.flush.isChecked())

    def edit_shortcuts(self):
        experiments = sorted(self.explist_model.backing_store.keys())
        self.shortcuts.edit(experiments)
