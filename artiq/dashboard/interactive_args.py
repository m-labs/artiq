import logging
import asyncio
from collections import OrderedDict

from PyQt6 import QtCore, QtWidgets, QtGui

from artiq.gui.models import DictSyncModel
from artiq.gui.entries import EntryTreeWidget, procdesc_to_entry
from artiq.gui.tools import LayoutWidget


logger = logging.getLogger(__name__)


class Model(DictSyncModel):
    def __init__(self, init):
        DictSyncModel.__init__(self, ["RID", "Title", "Args"], init)

    def convert(self, k, v, column):
        if column == 0:
            return k
        elif column == 1:
            rid = k[0]
            txt = ": " + v["title"] if v["title"] != "" else ""
            return str(rid) + txt
        elif column == 2:
            return v["arglist_desc"]
        else:
            raise ValueError

    def sort_key(self, k, v):
        return k


class _InteractiveArgsRequest(EntryTreeWidget):
    supplied = QtCore.pyqtSignal(tuple, dict)
    cancelled = QtCore.pyqtSignal(tuple)

    def __init__(self, request, arglist_desc):
        EntryTreeWidget.__init__(self)
        self.request = request
        self.arguments = dict()
        for key, procdesc, group, tooltip in arglist_desc:
            self.arguments[key] = {"desc": procdesc, "group": group, "tooltip": tooltip}
            self.set_argument(key, self.arguments[key])
        self.quickStyleClicked.connect(self.supply)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton))
        cancel_btn.clicked.connect(self.cancel)
        supply_btn = QtWidgets.QPushButton("Supply")
        supply_btn.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DialogOkButton))
        supply_btn.clicked.connect(self.supply)
        buttons = LayoutWidget()
        buttons.addWidget(cancel_btn, 1, 1)
        buttons.addWidget(supply_btn, 1, 2)
        buttons.layout.setColumnStretch(0, 1)
        buttons.layout.setColumnStretch(1, 0)
        buttons.layout.setColumnStretch(2, 0)
        buttons.layout.setColumnStretch(3, 1)
        self.setItemWidget(self.bottom_item, 1, buttons)

    def supply(self):
        argument_values = dict()
        for key, argument in self.arguments.items():
            entry_cls = procdesc_to_entry(argument["desc"])
            argument_values[key] = entry_cls.state_to_value(argument["state"])
        self.supplied.emit(self.request, argument_values)

    def cancel(self):
        self.cancelled.emit(self.request)


class _InteractiveArgsView(QtWidgets.QStackedWidget):
    supplied = QtCore.pyqtSignal(tuple, dict)
    cancelled = QtCore.pyqtSignal(tuple)

    def __init__(self, dock):
        QtWidgets.QStackedWidget.__init__(self)
        self.tabs = QtWidgets.QTabWidget()
        self.dock = dock
        self.default_label = QtWidgets.QLabel("No pending interactive arguments requests.")
        self.default_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        font = QtGui.QFont(self.default_label.font())
        font.setItalic(True)
        self.default_label.setFont(font)
        self.addWidget(self.tabs)
        self.addWidget(self.default_label)
        self.model = Model({})

    def setModel(self, model):
        self.setCurrentIndex(1)
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            self.tabs.removeTab(i)
            widget.deleteLater()
        self.model = model
        self.model.rowsInserted.connect(self.rowsInserted)
        self.model.rowsRemoved.connect(self.rowsRemoved)
        for i in range(self.model.rowCount(QtCore.QModelIndex())):
            self._insert_widget(i)

    def _insert_widget(self, row):
        request = self.model.data(self.model.index(row, 0),
                              QtCore.Qt.ItemDataRole.DisplayRole)
        title = self.model.data(self.model.index(row, 1),
                                QtCore.Qt.ItemDataRole.DisplayRole)
        arglist_desc = self.model.data(self.model.index(row, 2),
                                       QtCore.Qt.ItemDataRole.DisplayRole)
        inter_args_request = _InteractiveArgsRequest(request, arglist_desc)
        inter_args_request.supplied.connect(self.supplied)
        inter_args_request.cancelled.connect(self.cancelled)
        self.tabs.insertTab(row, inter_args_request, title)

        widget_state = self.dock.get_stored_state(request)
        if widget_state:
            inter_args_request.restore_state(widget_state)

    def rowsInserted(self, parent, first, last):
        assert first == last
        self.setCurrentIndex(0)
        self._insert_widget(first)

    def rowsRemoved(self, parent, first, last):
        assert first == last
        widget = self.tabs.widget(first)
        self.tabs.removeTab(first)
        widget.deleteLater()
        if self.tabs.count() == 0:
            self.setCurrentIndex(1)


class _LRUDict(OrderedDict):
    def __init__(self, size_limit=100):
        super().__init__()
        self.size_limit = size_limit

    def __setitem__(self, key, value):
        if key in self:
            self.pop(key)
        super().__setitem__(key, value)
        if len(self) > self.size_limit:
            self.popitem(last=False)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value


class InteractiveArgsDock(QtWidgets.QDockWidget):
    def __init__(self, interactive_args_sub, interactive_args_rpc):
        QtWidgets.QDockWidget.__init__(self, "Interactive Args")
        self.widget_states = _LRUDict()
        self.setObjectName("Interactive Args")
        self.setFeatures(
            self.DockWidgetFeature.DockWidgetMovable | self.DockWidgetFeature.DockWidgetFloatable)
        self.interactive_args_rpc = interactive_args_rpc
        self.request_view = _InteractiveArgsView(self)
        self.request_view.supplied.connect(self.supply)
        self.request_view.cancelled.connect(self.cancel)
        self.setWidget(self.request_view)
        interactive_args_sub.add_setmodel_callback(self.request_view.setModel)

    def _get_storage_key(self, request):
        filename, pipeline = request[1], request[2]
        return (filename, pipeline)

    def save_state(self):
        return {"widget_states": dict(self.widget_states)}

    def restore_state(self, state):
        self.widget_states.update(state.get("widget_states", {}))

    def get_stored_state(self, request):
        storage_key = self._get_storage_key(request)
        return self.widget_states.get(storage_key)

    def supply(self, request, values):
        widget = self.request_view.tabs.currentWidget()
        if widget:
            storage_key = self._get_storage_key(request)
            self.widget_states[storage_key] = widget.save_state()
        asyncio.ensure_future(self._supply_task(request, values))

    async def _supply_task(self, request, values):
        try:
            await self.interactive_args_rpc.supply(request, values)
        except Exception:
            logger.error("failed to supply interactive arguments for experiment: %d",
                         request[0], exc_info=True)

    def cancel(self, request):
        asyncio.ensure_future(self._cancel_task(request))

    async def _cancel_task(self, request):
        try:
            await self.interactive_args_rpc.cancel(request)
        except Exception:
            logger.error("failed to cancel interactive args request for experiment: %d",
                         request[0], exc_info=True)
