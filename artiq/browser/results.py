import logging
import os

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
                logger.warning("unable to read thumbnail", exc_info=True)
                return
            pix = QtGui.QPixmap.fromImage(img)
            return QtGui.QIcon(pix)


class ResultsDock(QtWidgets.QDockWidget):
    def __init__(self, datasets, main_window, root=None):
        QtWidgets.QDockWidget.__init__(self, "Results")
        self.setObjectName("Results")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        self.splitter = QtWidgets.QSplitter()
        self.setWidget(self.splitter)

        if root is None:
            root = QtCore.QDir.currentPath()

        self.datasets = datasets
        self.main_window = main_window

        self.rt_model = QtWidgets.QFileSystemModel()
        self.rt_model.setFilter(QtCore.QDir.NoDotAndDotDot |
                                QtCore.QDir.AllDirs)

        self.rt = QtWidgets.QTreeView()
        self.rt.setModel(self.rt_model)
        self.rt.setRootIndex(self.rt_model.setRootPath(root))
        self.rt.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rt.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rt.selectionModel().currentChanged.connect(
            self.tree_current_changed)
        self.rt.setRootIsDecorated(False)
        self.splitter.addWidget(self.rt)

        self.rl = QtWidgets.QListView()
        self.rl.setViewMode(QtWidgets.QListView.IconMode)
        l = QtGui.QFontMetrics(self.font()).lineSpacing()
        self.rl.setIconSize(QtCore.QSize(20*l, 15*l))
        self.rl.setFlow(QtWidgets.QListView.LeftToRight)
        self.rl.setWrapping(True)
        self.tree_current_changed(self.rt.currentIndex(), None)
        self.splitter.addWidget(self.rl)

    def showEvent(self, ev):
        self.rt.hideColumn(1)
        self.rt.hideColumn(2)
        self.rt.hideColumn(3)

    def tree_current_changed(self, current, previous):
        path = self.rt_model.filePath(current)
        # create a new model for the ListView here
        self.rl_model = QtWidgets.QFileSystemModel()
        self.rl_model.setFilter(QtCore.QDir.Files)
        self.rl_model.setNameFilters(["*.h5"])
        self.rl_model.setNameFilterDisables(False)
        self.rl_model.setIconProvider(ResultIconProvider())
        self.rl.setModel(self.rl_model)
        self.rl.setRootIndex(self.rl_model.setRootPath(path))
        self.rl.selectionModel().currentChanged.connect(
            self.list_current_changed)

    def list_current_changed(self, current, previous):
        info = self.rl_model.fileInfo(current)
        logger.info("opening %s", info.filePath())
        if not (info.isFile() and info.isReadable() and
                info.suffix() == "h5"):
            return
        try:
            f = h5py.File(info.filePath(), "r")
        except:
            logger.warning("unable to read HDF5 file", exc_info=True)
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

    def select(self, path):
        idx = self.rt_model.index(os.path.dirname(path))
        self.rt.expand(idx)
        self.rt.scrollTo(idx)
        self.rt.setCurrentIndex(idx)
        self.rl.setCurrentIndex(self.rl_model.index(path))

    def save_state(self):
        return {
            "selected": self.rl_model.filePath(self.rt.currentIndex()),
            "header": bytes(self.rt.header().saveState()),
            "splitter": bytes(self.splitter.saveState()),
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
            self.splitter.restoreState(QtCore.QByteArray(splitter))
