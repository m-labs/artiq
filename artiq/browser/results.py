import logging
import threading

import h5py
from PyQt5 import QtCore, QtWidgets, QtGui

logger = logging.getLogger(__name__)


class ResultError(Exception):
    pass


class ResultIconProvider(QtWidgets.QFileIconProvider):
    def icon(self, info):
        try:
            if not (info.isFile() and info.isReadable() and
                    info.suffix() == "h5"):
                raise ResultError
            with h5py.File(info.filePath(), "r") as f:
                if "thumbnail" not in f:
                    raise ResultError
                d = f["thumbnail"]
                if "extension" not in d.attrs:
                    raise ResultError
                img = QtGui.QImage.fromData(d.value, d.attrs["extension"])
                pix = QtGui.QPixmap.fromImage(img)
                return QtGui.QIcon(pix)
        except ResultError:
            return QtWidgets.QFileIconProvider.icon(self, info)


class ResultsBrowser(QtWidgets.QSplitter):
    def __init__(self, datasets):
        QtWidgets.QSplitter.__init__(self)

        self.datasets = datasets

        self.rt_model = QtWidgets.QFileSystemModel()
        self.rt_model.setRootPath(QtCore.QDir.currentPath())
        self.rt_model.setNameFilters(["*.h5"])
        self.rt_model.setNameFilterDisables(False)
        self.icon_provider = ResultIconProvider()
        self.rt_model.setIconProvider(self.icon_provider)

        self.rt = QtWidgets.QTreeView()
        self.rt.setModel(self.rt_model)
        self.rt.setRootIndex(self.rt_model.index(QtCore.QDir.currentPath()))
        self.rt.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rt.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rt.selectionModel().currentChanged.connect(
            self.current_changed)
        self.rt.setRootIsDecorated(False)
        self.addWidget(self.rt)

        self.rl = QtWidgets.QListView()
        self.rl.setViewMode(QtWidgets.QListView.IconMode)
        self.rl.setModel(self.rt_model)
        self.rl.setSelectionModel(self.rt.selectionModel())
        self.rl.setRootIndex(self.rt.rootIndex())
        l = QtGui.QFontMetrics(self.font()).lineSpacing()
        self.rl.setIconSize(QtCore.QSize(20*l, 20*l))
        self.rl.setWrapping(True)
        self.rl.setFlow(QtWidgets.QListView.LeftToRight)
        self.addWidget(self.rl)

    def showEvent(self, ev):
        if hasattr(self, "_shown"):
            return
        self._shown = True
        self.rt.hideColumn(1)
        self.rt.hideColumn(2)
        self.rt.hideColumn(3)
        self.rt.scrollTo(self.rt.selectionModel().currentIndex())

    def cleanup(self):
        pass

    def current_changed(self, current, previous):
        info = self.rt_model.fileInfo(current)
        logger.info("opening %s", info.filePath())
        try:
            if not (info.isFile() and info.isReadable() and
                    info.suffix() == "h5"):
                raise ResultError
            with h5py.File(info.filePath(), "r") as f:
                rd = {}
                if "datasets" not in f:
                    raise ResultError
                group = f["datasets"]
                for k in group:
                    rd[k] = True, group[k].value
                self.datasets.init(rd)
        except ResultError:
            pass

    def select(self, path):
        self.rt.selectionModel().setCurrentIndex(
            self.rt_model.index(path),
            QtCore.QItemSelectionModel.ClearAndSelect)

    def save_state(self):
        return {
            "selected": self.rt_model.filePath(
                self.rt.selectionModel().currentIndex()),
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
