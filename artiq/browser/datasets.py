import logging
import asyncio

from PyQt5 import QtCore, QtWidgets

from sipyco.pc_rpc import AsyncioClient as RPCClient

from artiq.tools import short_format
from artiq.gui.tools import LayoutWidget, QRecursiveFilterProxyModel
from artiq.gui.models import DictSyncTreeSepModel

# reduced read-only version of artiq.dashboard.datasets


logger = logging.getLogger(__name__)


class Model(DictSyncTreeSepModel):
    def __init__(self,  init):
        DictSyncTreeSepModel.__init__(self, ".", ["Dataset", "Value"], init)

    def convert(self, k, v, column):
        return short_format(v[1])


class DatasetsDock(QtWidgets.QDockWidget):
    def __init__(self, datasets_sub, master_host, master_port):
        QtWidgets.QDockWidget.__init__(self, "Datasets")
        self.setObjectName("Datasets")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

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

        metadata_grid = LayoutWidget()
        self.metadata = {}
        for i, label in enumerate("artiq_version repo_rev file class_name "
                                  "rid start_time".split()):
            metadata_grid.addWidget(QtWidgets.QLabel(label), i, 0)
            v = QtWidgets.QLabel()
            v.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            metadata_grid.addWidget(v, i, 1)
            self.metadata[label] = v
        grid.addWidget(metadata_grid, 2, 0)

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        upload_action = QtWidgets.QAction("Upload dataset to master",
                                          self.table)
        upload_action.triggered.connect(self.upload_clicked)
        self.table.addAction(upload_action)

        self.set_model(Model(dict()))
        datasets_sub.add_setmodel_callback(self.set_model)

        self.master_host = master_host
        self.master_port = master_port

    def _search_datasets(self):
        if hasattr(self, "table_model_filter"):
            self.table_model_filter.setFilterFixedString(
                self.search.displayText())

    def metadata_changed(self, new):
        for k, v in new.items():
            self.metadata[k].setText("{}".format(v))

    def set_model(self, model):
        self.table_model = model
        self.table_model_filter = QRecursiveFilterProxyModel()
        self.table_model_filter.setSourceModel(self.table_model)
        self.table.setModel(self.table_model_filter)

    async def _upload_dataset(self, name, value,):
        logger.info("Uploading dataset '%s' to master...", name)
        try:
            remote = RPCClient()
            await remote.connect_rpc(self.master_host, self.master_port,
                                     "master_dataset_db")
            try:
                await remote.set(name, value)
            finally:
                remote.close_rpc()
        except:
            logger.error("Failed uploading dataset '%s'",
                         name, exc_info=True)
        else:
            logger.info("Finished uploading dataset '%s'", name)

    def upload_clicked(self):
        idx = self.table.selectedIndexes()
        if idx:
            idx = self.table_model_filter.mapToSource(idx[0])
            key = self.table_model.index_to_key(idx)
            if key is not None:
                persist, value = self.table_model.backing_store[key]
                asyncio.ensure_future(self._upload_dataset(key, value))

    def save_state(self):
        return bytes(self.table.header().saveState())

    def restore_state(self, state):
        self.table.header().restoreState(QtCore.QByteArray(state))
