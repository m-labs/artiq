import logging
import asyncio

from PyQt5 import QtCore, QtWidgets, QtGui

from artiq.gui.models import DictSyncModel
from artiq.gui.entries import EntryTreeWidget, procdesc_to_entry


logger = logging.getLogger(__name__)


class Model(DictSyncModel):
    def __init__(self, init):
        DictSyncModel.__init__(self, ["RID", "Title", "Args"], init)

    def convert(self, k, v, column):
        if column == 0:
            return k
        elif column == 1:
            txt = ": " + v["title"] if v["title"] != "" else ""
            return str(k) + txt
        elif column == 2:
            return v["arglist_desc"]
        else:
            raise ValueError

    def sort_key(self, k, v):
        return k


class _InteractiveArgsRequest(QtWidgets.QWidget):
    supplied = QtCore.pyqtSignal(int, dict)
    cancelled = QtCore.pyqtSignal(int)

    def __init__(self, rid, arglist_desc):
        QtWidgets.QWidget.__init__(self)
        self.rid = rid
        self.arguments = dict()
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        self.entry_tree = EntryTreeWidget()
        layout.addWidget(self.entry_tree, 0, 0, 1, 2)
        for key, procdesc, group, tooltip in arglist_desc:
            self.arguments[key] = {"desc": procdesc, "group": group, "tooltip": tooltip}
            self.entry_tree.set_argument(key, self.arguments[key])
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_DialogCancelButton))
        self.cancel_btn.clicked.connect(self.cancel)
        layout.addWidget(self.cancel_btn, 1, 0, 1, 1)
        self.supply_btn = QtWidgets.QPushButton("Supply")
        self.supply_btn.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_DialogOkButton))
        self.supply_btn.clicked.connect(self.supply)
        layout.addWidget(self.supply_btn, 1, 1, 1, 1)

    def supply(self):
        argument_values = dict()
        for key, argument in self.arguments.items():
            entry_cls = procdesc_to_entry(argument["desc"])
            argument_values[key] = entry_cls.state_to_value(argument["state"])
        self.supplied.emit(self.rid, argument_values)

    def cancel(self):
        self.cancelled.emit(self.rid)


class _InteractiveArgsView(QtWidgets.QTabWidget):
    supplied = QtCore.pyqtSignal(int, dict)
    cancelled = QtCore.pyqtSignal(int)

    def __init__(self):
        QtWidgets.QTabWidget.__init__(self)
        self.model = Model({})

    def setModel(self, model):
        for i in range(self.count()):
            widget = self.widget(i)
            self.removeTab(i)
            widget.deleteLater()
        self.model = model
        self.model.rowsInserted.connect(self.rowsInserted)
        self.model.rowsRemoved.connect(self.rowsRemoved)
        for i in range(self.model.rowCount(QtCore.QModelIndex())):
            self._insert_widget(i)

    def _insert_widget(self, row):
        rid = self.model.data(self.model.index(row, 0), QtCore.Qt.DisplayRole)
        title = self.model.data(self.model.index(row, 1), QtCore.Qt.DisplayRole)
        arglist_desc = self.model.data(self.model.index(row, 2), QtCore.Qt.DisplayRole)
        inter_args_request = _InteractiveArgsRequest(rid, arglist_desc)
        inter_args_request.supplied.connect(self.supplied)
        inter_args_request.cancelled.connect(self.cancelled)
        self.insertTab(row, inter_args_request, title)

    def rowsInserted(self, parent, first, last):
        assert first == last
        self._insert_widget(first)

    def rowsRemoved(self, parent, first, last):
        assert first == last
        widget = self.widget(first)
        self.removeTab(first)
        widget.deleteLater()


class InteractiveArgsDock(QtWidgets.QDockWidget):
    def __init__(self, interactive_args_sub, interactive_args_rpc):
        QtWidgets.QDockWidget.__init__(self, "Interactive Args")
        self.setObjectName("Interactive Args")
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        self.interactive_args_rpc = interactive_args_rpc
        self.request_view = _InteractiveArgsView()
        self.request_view.supplied.connect(self.supply)
        self.request_view.cancelled.connect(self.cancel)
        self.setWidget(self.request_view)
        interactive_args_sub.add_setmodel_callback(self.request_view.setModel)

    def supply(self, rid, values):
        asyncio.ensure_future(self._supply_task(rid, values))

    async def _supply_task(self, rid, values):
        try:
            await self.interactive_args_rpc.supply(rid, values)
        except Exception:
            logger.error("failed to supply interactive arguments for experiment: %d",
                         rid, exc_info=True)

    def cancel(self, rid):
        asyncio.ensure_future(self._cancel_task(rid))

    async def _cancel_task(self, rid):
        try:
            await self.interactive_args_rpc.cancel(rid)
        except Exception:
            logger.error("failed to cancel interactive args request for experiment: %d",
                         rid, exc_info=True)
