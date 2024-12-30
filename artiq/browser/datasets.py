import logging
import asyncio

from PyQt6 import QtCore, QtGui, QtWidgets

from sipyco.pc_rpc import AsyncioClient as RPCClient

from artiq.tools import short_format
from artiq.gui.tools import LayoutWidget
from artiq.gui.models import DictSyncTreeSepModel

# reduced read-only version of artiq.dashboard.datasets


logger = logging.getLogger(__name__)


class Model(DictSyncTreeSepModel):
    def __init__(self,  init):
        DictSyncTreeSepModel.__init__(self, ".", ["Dataset", "Value"], init)

    def convert(self, k, v, column):
        return short_format(v[1], v[2])


class DatasetCtl:
    def __init__(self, master_host, master_port):
        self.master_host = master_host
        self.master_port = master_port

    async def _execute_rpc(self, op_name, key_or_mod, value=None, persist=None, metadata=None):
        logger.info("Starting %s operation on %s", op_name, key_or_mod)
        try:
            remote = RPCClient()
            await remote.connect_rpc(self.master_host, self.master_port,
                                     "dataset_db")
            try:
                if op_name == "set":
                    await remote.set(key_or_mod, value, persist, metadata)
                elif op_name == "update":
                    await remote.update(key_or_mod)
                else:
                    logger.error("Invalid operation: %s", op_name)
                    return
            finally:
                remote.close_rpc()
        except:
            logger.error("Failed %s operation on %s", op_name,
                        key_or_mod, exc_info=True)
        else:
            logger.info("Finished %s operation on %s", op_name,
                     key_or_mod)

    async def set(self, key, value, persist=None, metadata=None):
        await self._execute_rpc("set", key, value, persist, metadata)

    async def update(self, mod):
        await self._execute_rpc("update", mod)


class DatasetsDock(QtWidgets.QDockWidget):
    def __init__(self, dataset_sub, dataset_ctl):
        QtWidgets.QDockWidget.__init__(self, "Datasets")
        self.setObjectName("Datasets")
        self.setFeatures(self.DockWidgetFeature.DockWidgetMovable |
                         self.DockWidgetFeature.DockWidgetFloatable)

        grid = LayoutWidget()
        self.setWidget(grid)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("search...")
        self.search.editingFinished.connect(self._search_datasets)
        grid.addWidget(self.search, 0, 0)

        self.table = QtWidgets.QTreeView()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        grid.addWidget(self.table, 1, 0)

        metadata_grid = LayoutWidget()
        self.metadata = {}
        for i, label in enumerate("artiq_version repo_rev file class_name "
                                  "rid start_time".split()):
            metadata_grid.addWidget(QtWidgets.QLabel(label), i, 0)
            v = QtWidgets.QLabel()
            v.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            metadata_grid.addWidget(v, i, 1)
            self.metadata[label] = v
        grid.addWidget(metadata_grid, 2, 0)

        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        upload_action = QtGui.QAction("Upload dataset to master",
                                          self.table)
        upload_action.triggered.connect(self.upload_clicked)
        self.table.addAction(upload_action)

        self.set_model(Model(dict()))
        dataset_sub.add_setmodel_callback(self.set_model)

        self.dataset_ctl = dataset_ctl

    def _search_datasets(self):
        if hasattr(self, "table_model_filter"):
            self.table_model_filter.setFilterFixedString(
                self.search.displayText())

    def metadata_changed(self, new):
        for k, v in new.items():
            self.metadata[k].setText("{}".format(v))

    def set_model(self, model):
        self.table_model = model
        self.table_model_filter = QtCore.QSortFilterProxyModel()
        self.table_model_filter.setRecursiveFilteringEnabled(True)
        self.table_model_filter.setSourceModel(self.table_model)
        self.table.setModel(self.table_model_filter)

    def upload_clicked(self):
        idx = self.table.selectedIndexes()
        if idx:
            idx = self.table_model_filter.mapToSource(idx[0])
            key = self.table_model.index_to_key(idx)
            if key is not None:
                persist, value, metadata = self.table_model.backing_store[key]
                asyncio.ensure_future(self.dataset_ctl.set(key, value, metadata=metadata))

    def save_state(self):
        return bytes(self.table.header().saveState())

    def restore_state(self, state):
        self.table.header().restoreState(QtCore.QByteArray(state))
