import logging
import os

import h5py
from PyQt5 import QtCore, QtWidgets, QtGui

logger = logging.getLogger(__name__)


class ThumbnailIconProvider(QtWidgets.QFileIconProvider):
    def icon(self, info):
        icon = self.hdf5_thumbnail(info)
        if icon is None:
            icon = QtWidgets.QFileIconProvider.icon(self, info)
        return icon

    def hdf5_thumbnail(self, info):
        if not (info.isFile() and info.isReadable() and
                info.suffix() == "h5"):
            return
        try:
            f = h5py.File(info.filePath(), "r")
        except:
            return
        with f:
            try:
                t = f["datasets/thumbnail"]
            except KeyError:
                return
            try:
                img = QtGui.QImage.fromData(t.value)
            except:
                logger.warning("unable to read thumbnail from %s",
                               info.filePath(), exc_info=True)
                return
            pix = QtGui.QPixmap.fromImage(img)
            return QtGui.QIcon(pix)


class DirsOnlyProxy(QtCore.QSortFilterProxyModel):
    def filterAcceptsRow(self, row, parent):
        idx = self.sourceModel().index(row, 0, parent)
        if not self.sourceModel().fileInfo(idx).isDir():
            return False
        return QtCore.QSortFilterProxyModel.filterAcceptsRow(self, row, parent)


class FilesDock(QtWidgets.QDockWidget):
    def __init__(self, datasets, main_window, root=""):
        QtWidgets.QDockWidget.__init__(self, "Files")
        self.setObjectName("Files")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        self.splitter = QtWidgets.QSplitter()
        self.setWidget(self.splitter)

        self.datasets = datasets
        self.main_window = main_window

        self.model = QtWidgets.QFileSystemModel()
        self.model.setFilter(QtCore.QDir.Drives | QtCore.QDir.NoDotAndDotDot |
                             QtCore.QDir.AllDirs | QtCore.QDir.Files)
        self.model.setNameFilterDisables(False)
        self.model.setIconProvider(ThumbnailIconProvider())

        self.rt = QtWidgets.QTreeView()
        rt_model = DirsOnlyProxy()
        rt_model.setDynamicSortFilter(True)
        rt_model.setSourceModel(self.model)
        self.rt.setModel(rt_model)
        self.model.directoryLoaded.connect(
            lambda: self.rt.resizeColumnToContents(0))
        self.rt.setAnimated(False)
        self.rt.setRootIndex(rt_model.mapFromSource(
            self.model.setRootPath(root)))
        self.rt.setSelectionBehavior(self.rt.SelectRows)
        self.rt.setSelectionMode(self.rt.SingleSelection)
        self.rt.selectionModel().currentChanged.connect(
            self.tree_current_changed)
        self.rt.setRootIsDecorated(False)
        for i in range(1, 4):
            self.rt.hideColumn(i)
        self.splitter.addWidget(self.rt)

        self.rl = QtWidgets.QListView()
        self.rl.setViewMode(QtWidgets.QListView.IconMode)
        l = QtGui.QFontMetrics(self.font()).lineSpacing()
        self.rl.setIconSize(QtCore.QSize(20*l, 15*l))
        self.rl.setFlow(QtWidgets.QListView.LeftToRight)
        self.rl.setWrapping(True)
        self.rl.setModel(self.model)
        self.rl.selectionModel().currentChanged.connect(
            self.list_current_changed)
        self.splitter.addWidget(self.rl)

    def tree_current_changed(self, current, previous):
        idx = self.rt.model().mapToSource(current)
        self.rl.setRootIndex(idx)

    def list_current_changed(self, current, previous):
        info = self.model.fileInfo(current)
        logger.info("opening %s", info.filePath())
        if not (info.isFile() and info.isReadable() and
                info.suffix() == "h5"):
            return
        try:
            f = h5py.File(info.filePath(), "r")
        except:
            logger.warning("unable to read HDF5 file %s", info.filePath(),
                           exc_info=True)
            return
        with f:
            rd = {}
            try:
                group = f["datasets"]
            except KeyError:
                return
            for k in f["datasets"]:
                rd[k] = True, group[k].value
            self.datasets.init(rd)

    def select_dir(self, path):
        if not os.path.exists(path):
            return
        idx = self.model.index(path)
        self.rl.setRootIndex(idx)
        idx = self.rt.model().mapFromSource(idx)
        self.rt.expand(idx)

        def scroll_when_loaded(p):
            if p != path:
                return
            self.model.directoryLoaded.disconnect(scroll_when_loaded)
            QtCore.QTimer.singleShot(
                100, lambda:
                self.rt.scrollTo(self.rt.model().mapFromSource(
                    self.model.index(path)), self.rt.PositionAtCenter))
        self.model.directoryLoaded.connect(scroll_when_loaded)
        self.rt.setCurrentIndex(idx)

    def select_file(self, path):
        if not os.path.exists(path):
            return
        self.select_dir(os.path.dirname(path))
        self.rl.setCurrentIndex(self.model.index(path))

    def save_state(self):
        return {
            "dir": self.model.filePath(self.rt.model().mapToSource(
                self.rt.currentIndex())),
            "file": self.model.filePath(self.rl.currentIndex()),
            "header": bytes(self.rt.header().saveState()),
            "splitter": bytes(self.splitter.saveState()),
        }

    def restore_state(self, state):
        dir = state.get("dir")
        if dir:
            self.select_dir(dir)
        file = state.get("file")
        if file:
            self.select_file(file)
        header = state.get("header")
        if header:
            self.rt.header().restoreState(QtCore.QByteArray(header))
        splitter = state.get("splitter")
        if splitter:
            self.splitter.restoreState(QtCore.QByteArray(splitter))
