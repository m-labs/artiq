import logging

import h5py
from PyQt5 import QtCore, QtWidgets, QtGui

logger = logging.getLogger(__name__)


class ResultIconProvider(QtWidgets.QFileIconProvider):
    def icon(self, info):
        icon = self.hdf5_thumbnail(info)
        if icon is None:
            icon = QtWidgets.QFileIconProvider.icon(self, info)
        return icon

    def hdf5_thumbnail(self, info):
        if not (info.isFile() and info.isReadable() and
                info.suffix() == "h5"):
            return
        with h5py.File(info.filePath(), "r") as f:
            if "thumbnail" not in f:
                return
            img = QtGui.QImage.fromData(f["thumbnail"].value)
            pix = QtGui.QPixmap.fromImage(img)
            return QtGui.QIcon(pix)


class DirsOnly(QtCore.QSortFilterProxyModel):
    def filterAcceptsRow(self, row, parent):
        m = self.sourceModel()
        if not m.isDir(m.index(row, 0, parent)):
            return False
        return QtCore.QSortFilterProxyModel.filterAcceptsRow(self, row, parent)


class FilesOnly(QtCore.QSortFilterProxyModel):
    _root_idx = None

    def filterAcceptsRow(self, row, parent):
        if self._root_idx is not None:
            model = self.sourceModel()
            idx = model.index(row, 0, parent)
            if idx == self._root_idx:
                return True
            if model.isDir(idx):
                print("false", model.filePath(idx),
                      model.filePath(self._root_idx))
                return False
        return QtCore.QSortFilterProxyModel.filterAcceptsRow(self, row, parent)

    def setRootIndex(self, idx):
        self._root_idx = idx


class ResultsBrowser(QtWidgets.QSplitter):
    def __init__(self, datasets):
        QtWidgets.QSplitter.__init__(self)

        self.datasets = datasets

        self.model = QtWidgets.QFileSystemModel()
        self.model.setRootPath(QtCore.QDir.currentPath())
        self.model.setNameFilters(["*.h5"])
        self.model.setNameFilterDisables(False)
        self.model.setIconProvider(ResultIconProvider())

        self.rt = QtWidgets.QTreeView()
        self.rt_model = DirsOnly()
        self.rt_model.setSourceModel(self.model)
        self.rt.setModel(self.rt_model)
        self.rt.setRootIndex(self.rt_model.mapFromSource(self.model.index(
            QtCore.QDir.currentPath())))
        self.rt.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rt.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rt.selectionModel().currentChanged.connect(
            self.tree_current_changed)
        self.rt.setRootIsDecorated(False)
        self.addWidget(self.rt)

        self.rl = QtWidgets.QListView()
        self.rl_model = FilesOnly()
        self.rl_model.setSourceModel(self.model)
        self.rl.setModel(self.rl_model)
        self.rl.setViewMode(QtWidgets.QListView.IconMode)
        l = QtGui.QFontMetrics(self.font()).lineSpacing()
        self.rl.setIconSize(QtCore.QSize(20*l, 15*l))
        self.rl.setFlow(QtWidgets.QListView.LeftToRight)
        self.rl.setWrapping(True)
        self.rl.selectionModel().currentChanged.connect(
            self.list_current_changed)
        self.addWidget(self.rl)

    def showEvent(self, ev):
        if hasattr(self, "_shown"):
            return
        self._shown = True
        self.rt.hideColumn(1)
        self.rt.hideColumn(2)
        self.rt.hideColumn(3)
        self.rt.scrollTo(self.rt.selectionModel().currentIndex())

    def tree_current_changed(self, current, previous):
        i = self.rt_model.mapToSource(current)
        self.rl_model.setRootIndex(i)
        j = self.rl_model.mapFromSource(i)
        print("root", self.model.filePath(i),
                      i.isValid())
        self.rl.setRootIndex(j)

    def list_current_changed(self, current, previous):
        info = self.model.fileInfo(self.rl_model.mapToSource(current))
        logger.info("opening %s", info.filePath())
        if not (info.isFile() and info.isReadable() and
                info.suffix() == "h5"):
            return
        with h5py.File(info.filePath(), "r") as f:
            rd = {}
            if "datasets" not in f:
                return
            group = f["datasets"]
            for k in group:
                rd[k] = True, group[k].value
            self.datasets.init(rd)

    def select(self, path):
        idx = self.rt_model.mapFromSource(self.model.index(path))
        self.rt.scrollTo(idx)
        self.rt.expand(idx)
        self.rt.selectionModel().setCurrentIndex(
            idx, QtCore.QItemSelectionModel.ClearAndSelect)

    def save_state(self):
        return {
            "selected": self.model.filePath(self.rt_model.mapToSource(
                self.rt.selectionModel().currentIndex())),
            "header": bytes(self.rt.header().saveState()),
            "splitter": bytes(self.saveState()),
        }

    def restore_state(self, state):
        selected = state.get("selected")
        if selected:
            self.select(selected)
        header = state.get("header")
        if header:
            self.rt.header().restoreState(QtCore.QByteArray(header))
        splitter = state.get("splitter")
        if splitter:
            self.restoreState(QtCore.QByteArray(splitter))
