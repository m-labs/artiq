#!/usr/bin/env python3.5

import argparse
import asyncio
import atexit
import os

from PyQt5 import QtCore, QtGui, QtWidgets
from quamash import QEventLoop

from artiq import __artiq_dir__ as artiq_dir
from artiq.tools import *
from artiq.gui import (state, results,
                       datasets, applets)
from artiq.protocols.sync_struct import process_mod


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ results browser")
    parser.add_argument(
        "--db-file", default="artiq_browser.pyon",
        help="database file for local browser settings")
    parser.add_argument("PATH", nargs="?", help="browse path")
    verbosity_args(parser)
    return parser


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)

        icon = QtGui.QIcon(os.path.join(artiq_dir, "gui", "logo.svg"))
        self.setWindowIcon(icon)
        self.setWindowTitle("ARTIQ - Browser")

        qfm = QtGui.QFontMetrics(self.font())
        self.resize(140*qfm.averageCharWidth(), 38*qfm.lineSpacing())

        self.exit_request = asyncio.Event()

    def closeEvent(self, *args):
        self.exit_request.set()

    def save_state(self):
        return {
            "state": bytes(self.saveState()),
            "geometry": bytes(self.saveGeometry())
        }

    def restore_state(self, state):
        self.restoreGeometry(QtCore.QByteArray(state["geometry"]))
        self.restoreState(QtCore.QByteArray(state["state"]))


class MdiArea(QtWidgets.QMdiArea):
    def __init__(self):
        QtWidgets.QMdiArea.__init__(self)
        self.pixmap = QtGui.QPixmap(os.path.join(artiq_dir, "gui", "logo.svg"))

    def paintEvent(self, event):
        QtWidgets.QMdiArea.paintEvent(self, event)
        painter = QtGui.QPainter(self.viewport())
        x = (self.width() - self.pixmap.width())//2
        y = (self.height() - self.pixmap.height())//2
        painter.setOpacity(0.5)
        painter.drawPixmap(x, y, self.pixmap)


class LocalModelManager:
    def __init__(self, model_factory, notify_cb=None):
        self.model = None
        self._model_factory = model_factory
        self._setmodel_callbacks = []
        if notify_cb is None:
            notify_cb = []
        if not isinstance(notify_cb, list):
            notify_cb = [notify_cb]
        self.notify_cbs = notify_cb

    def init(self, struct):
        self._create_model(struct)
        mod = {"action": "init", "struct": struct}
        for notify_cb in self.notify_cbs:
            notify_cb(mod)

    def _create_model(self, init):
        self.model = self._model_factory(init)
        for cb in self._setmodel_callbacks:
            cb(self.model)
        return self.model

    def add_setmodel_callback(self, cb):
        self._setmodel_callbacks.append(cb)
        if self.model is not None:
            cb(self.model)


def main():
    # initialize application
    args = get_argparser().parse_args()
    init_logger(args)

    app = QtWidgets.QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)
    smgr = state.StateManager(args.db_file)

    datasets_sub = LocalModelManager(datasets.Model)

    # initialize main window
    main_window = MainWindow()
    smgr.register(main_window)
    status_bar = QtWidgets.QStatusBar()
    main_window.setStatusBar(status_bar)
    mdi_area = MdiArea()
    mdi_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    mdi_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    main_window.setCentralWidget(mdi_area)

    d_results = results.ResultsDock(datasets_sub)
    smgr.register(d_results)

    d_applets = applets.AppletsDock(main_window, datasets_sub)
    atexit_register_coroutine(d_applets.stop)
    smgr.register(d_applets)

    d_datasets = datasets.DatasetsDock(datasets_sub,
                                       None)  # TODO: datsets_ctl.delete()
    smgr.register(d_datasets)

    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, d_results)
    main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, d_applets)
    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, d_datasets)

    # load/initialize state
    if os.name == "nt":
        # HACK: show the main window before creating applets.
        # Otherwise, the windows of those applets that are in detached
        # QDockWidgets fail to be embedded.
        main_window.show()

    smgr.load()

    if args.PATH:
        d_results.select(args.PATH)

    smgr.start()
    atexit_register_coroutine(smgr.stop)

    # run
    main_window.show()
    loop.run_until_complete(main_window.exit_request.wait())

if __name__ == "__main__":
    main()
