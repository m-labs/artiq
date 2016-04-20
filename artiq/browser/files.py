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


class FilesDock(QtWidgets.QDockWidget):
    def __init__(self, datasets, main_window, path):
        QtWidgets.QDockWidget.__init__(self, "Files")
        self.setObjectName("Files")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        self.splitter = QtWidgets.QSplitter()
        self.setWidget(self.splitter)

        self.datasets = datasets
        self.main_window = main_window

        self.rt_model = QtWidgets.QFileSystemModel()
        self.rt_model.setFilter(QtCore.QDir.NoDotAndDotDot |
                                QtCore.QDir.AllDirs | QtCore.QDir.Drives)

        self.rt = QtWidgets.QTreeView()
        self.rt.setModel(self.rt_model)
        self.rt.setRootIndex(self.rt_model.setRootPath(""))
        self.rt.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rt.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rt.selectionModel().currentChanged.connect(
            self.tree_current_changed)
        self.rt.hideColumn(1)
        self.rt.hideColumn(2)
        self.rt.hideColumn(3)
        self.splitter.addWidget(self.rt)

        self.rl = QtWidgets.QListView()
        self.rl.setViewMode(QtWidgets.QListView.IconMode)
        l = QtGui.QFontMetrics(self.font()).lineSpacing()
        self.rl.setIconSize(QtCore.QSize(20*l, 15*l))
        self.rl.setFlow(QtWidgets.QListView.LeftToRight)
        self.rl.setWrapping(True)
        self.rl.setResizeMode(QtWidgets.QListView.Adjust)
        self.tree_current_changed(self.rt.currentIndex(), None)
        self.rl.activated.connect(self.open_experiment)
        self.splitter.addWidget(self.rl)

        if path is not None:
            self.select(path)
            self.already_selected = True
        else:
            self.already_selected = False

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

    def select(self, file_or_dir):
        file_or_dir = os.path.abspath(file_or_dir)
        if os.path.isdir(file_or_dir):
            idx = self.rt_model.index(file_or_dir)
            if idx.isValid():
                self.rt.expand(idx)
                self.rt.setCurrentIndex(idx)
                self.rt.scrollTo(idx)
        else:
            idx = self.rt_model.index(os.path.dirname(file_or_dir))
            if idx.isValid():
                self.rt.expand(idx)
                self.rt.setCurrentIndex(idx)
                self.rt.scrollTo(idx)

            idx = self.rl_model.index(file_or_dir)
            if idx.isValid():
                self.rl.setCurrentIndex(idx)
                self.rl.scrollTo(idx)

    def open_experiment(self, index):
        print(self.rl_model.filePath(index))

    def save_state(self):
        return {
            "selected": self.rl_model.filePath(self.rl.currentIndex()),
            "splitter": bytes(self.splitter.saveState()),
        }

    def restore_state(self, state):
        self.splitter.restoreState(QtCore.QByteArray(state["splitter"]))
        if not self.already_selected:
            self.select(state["selected"])
