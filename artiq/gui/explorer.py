import asyncio
import traceback

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.protocols import pyon
from artiq.gui.tools import DictSyncModel, force_spinbox_value
from artiq.gui.scan import ScanController


class _ExplistModel(DictSyncModel):
    def __init__(self, parent, init):
        DictSyncModel.__init__(self,
            ["Experiment"],
            parent, init)

    def sort_key(self, k, v):
        return k

    def convert(self, k, v, column):
        return k


class _FreeValueEntry(QtGui.QLineEdit):
    def __init__(self, procdesc):
        QtGui.QLineEdit.__init__(self)
        if "default" in procdesc:
            self.insert(pyon.encode(procdesc["default"]))

    def get_argument_value(self):
        return pyon.decode(self.text())


class _BooleanEntry(QtGui.QCheckBox):
    def __init__(self, procdesc):
        QtGui.QCheckBox.__init__(self)
        if "default" in procdesc:
            self.setChecked(procdesc["default"])

    def get_argument_value(self):
        return self.isChecked()


class _EnumerationEntry(QtGui.QComboBox):
    def __init__(self, procdesc):
        QtGui.QComboBox.__init__(self)
        self.choices = procdesc["choices"]
        self.addItems(self.choices)
        if "default" in procdesc:
            try:
                idx = self.choices.index(procdesc["default"])
            except:
                pass
            else:
                self.setCurrentIndex(idx)

    def get_argument_value(self):
        return self.choices[self.currentIndex()]


class _NumberEntry(QtGui.QDoubleSpinBox):
    def __init__(self, procdesc):
        QtGui.QDoubleSpinBox.__init__(self)
        if procdesc["step"] is not None:
            self.setSingleStep(procdesc["step"])
        if procdesc["min"] is not None:
            self.setMinimum(procdesc["min"])
        if procdesc["max"] is not None:
            self.setMaximum(procdesc["max"])
        if procdesc["unit"]:
            self.setSuffix(" " + procdesc["unit"])
        if "default" in procdesc:
            force_spinbox_value(self, procdesc["default"])

    def get_argument_value(self):
        return self.value()


class _StringEntry(QtGui.QLineEdit):
    def __init__(self, procdesc):
        QtGui.QLineEdit.__init__(self)
        if "default" in procdesc:
            self.insert(procdesc["default"])

    def get_argument_value(self):
        return self.text()


_procty_to_entry = {
    "FreeValue": _FreeValueEntry,
    "BooleanValue": _BooleanEntry,
    "EnumerationValue": _EnumerationEntry,
    "NumberValue": _NumberEntry,
    "StringValue": _StringEntry,
    "Scannable": ScanController
}


class _ArgumentSetter(LayoutWidget):
    def __init__(self, dialog_parent, arguments):
        LayoutWidget.__init__(self)
        self.dialog_parent = dialog_parent

        if not arguments:
            self.addWidget(QtGui.QLabel("No arguments"), 0, 0)

        self._args_to_entries = dict()
        for n, (name, procdesc) in enumerate(arguments):
            self.addWidget(QtGui.QLabel(name), n, 0)
            entry = _procty_to_entry[procdesc["ty"]](procdesc)
            self.addWidget(entry, n, 1)
            self._args_to_entries[name] = entry

    def get_argument_values(self):
        r = dict()
        for arg, entry in self._args_to_entries.items():
            try:
                r[arg] = entry.get_argument_value()
            except:
                msgbox = QtGui.QMessageBox(self.dialog_parent)
                msgbox.setWindowTitle("Error")
                msgbox.setText("Failed to obtain value for argument '{}'.\n{}"
                               .format(arg, traceback.format_exc()))
                msgbox.setStandardButtons(QtGui.QMessageBox.Ok)
                msgbox.show()
                return None
        return r


class ExplorerDock(dockarea.Dock):
    def __init__(self, dialog_parent, status_bar, schedule_ctl):
        dockarea.Dock.__init__(self, "Explorer", size=(1500, 500))

        self.dialog_parent = dialog_parent
        self.status_bar = status_bar
        self.schedule_ctl = schedule_ctl

        self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.addWidget(self.splitter)

        grid = LayoutWidget()
        self.splitter.addWidget(grid)

        self.el = QtGui.QListView()
        self.el.selectionChanged = self.update_argsetter
        grid.addWidget(self.el, 0, 0, colspan=4)

        self.datetime = QtGui.QDateTimeEdit()
        self.datetime.setDisplayFormat("MMM d yyyy hh:mm:ss")
        self.datetime.setCalendarPopup(True)
        self.datetime.setDate(QtCore.QDate.currentDate())
        self.datetime.dateTimeChanged.connect(self.enable_duedate)
        self.datetime_en = QtGui.QCheckBox("Due date:")
        grid.addWidget(self.datetime_en, 1, 0)
        grid.addWidget(self.datetime, 1, 1)

        self.priority = QtGui.QSpinBox()
        self.priority.setRange(-99, 99)
        grid.addWidget(QtGui.QLabel("Priority:"), 1, 2)
        grid.addWidget(self.priority, 1, 3)

        self.pipeline = QtGui.QLineEdit()
        self.pipeline.insert("main")
        grid.addWidget(QtGui.QLabel("Pipeline:"), 2, 0)
        grid.addWidget(self.pipeline, 2, 1)

        self.flush = QtGui.QCheckBox("Flush")
        grid.addWidget(self.flush, 2, 2, colspan=2)

        submit = QtGui.QPushButton("Submit")
        grid.addWidget(submit, 3, 0, colspan=4)
        submit.clicked.connect(self.submit_clicked)

        self.argsetter = _ArgumentSetter(self.dialog_parent, [])
        self.splitter.addWidget(self.argsetter)
        self.splitter.setSizes([grid.minimumSizeHint().width(), 1000])

    def update_argsetter(self, selected, deselected):
        selected = selected.indexes()
        if selected:
            row = selected[0].row()
            key = self.explist_model.row_to_key[row]
            expinfo = self.explist_model.backing_store[key]
            arguments = expinfo["arguments"]
            sizes = self.splitter.sizes()
            self.argsetter.deleteLater()
            self.argsetter = _ArgumentSetter(self.dialog_parent, arguments)
            self.splitter.insertWidget(1, self.argsetter)
            self.splitter.setSizes(sizes)

    def enable_duedate(self):
        self.datetime_en.setChecked(True)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.explist_subscriber = Subscriber("explist",
                                             self.init_explist_model)
        yield from self.explist_subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.explist_subscriber.close()

    def init_explist_model(self, init):
        self.explist_model = _ExplistModel(self.el, init)
        self.el.setModel(self.explist_model)
        return self.explist_model

    @asyncio.coroutine
    def submit(self, pipeline_name, file, class_name, arguments,
               priority, due_date, flush):
        expid = {
            "file": file,
            "class_name": class_name,
            "arguments": arguments,
        }
        rid = yield from self.schedule_ctl.submit(pipeline_name, expid,
                                                  priority, due_date, flush)
        self.status_bar.showMessage("Submitted RID {}".format(rid))

    def submit_clicked(self):
        idx = self.el.selectedIndexes()
        if idx:
            row = idx[0].row()
            key = self.explist_model.row_to_key[row]
            expinfo = self.explist_model.backing_store[key]
            if self.datetime_en.isChecked():
                due_date = self.datetime.dateTime().toMSecsSinceEpoch()/1000
            else:
                due_date = None
            arguments = self.argsetter.get_argument_values()
            if arguments is None:
                return
            asyncio.async(self.submit(self.pipeline.text(),
                                      expinfo["file"], expinfo["class_name"],
                                      arguments, self.priority.value(),
                                      due_date, self.flush.isChecked()))
