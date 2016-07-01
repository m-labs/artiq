#!/usr/bin/env python3.5

import argparse
import asyncio
import atexit
import os
import logging

from PyQt5 import QtCore, QtGui, QtWidgets
from quamash import QEventLoop

from artiq import __artiq_dir__ as artiq_dir
from artiq.tools import verbosity_args, atexit_register_coroutine
from artiq.gui import state, applets, models, log
from artiq.browser import datasets, files, experiments

logger = logging.getLogger(__name__)


def get_argparser():
    if os.name == "nt":
        default_db_file = os.path.expanduser("~\\artiq_browser.pyon")
    else:
        default_db_file = os.path.expanduser("~/.artiq_browser.pyon")

    parser = argparse.ArgumentParser(description="ARTIQ Browser")
    parser.add_argument("--db-file", default=default_db_file,
                        help="database file for local browser settings "
                        "(default: %(default)s)")
    parser.add_argument("--browse-root", default="",
                        help="root path for directory tree "
                        "(default %(default)s)")
    parser.add_argument("select", metavar="SELECT", nargs="?",
                        help="directory to browse or file to load")
    verbosity_args(parser)
    return parser


class Browser(QtWidgets.QMainWindow):
    def __init__(self, datasets_sub, browse_root, select):
        QtWidgets.QMainWindow.__init__(self)

        icon = QtGui.QIcon(os.path.join(artiq_dir, "gui", "logo.svg"))
        self.setWindowIcon(icon)
        self.setWindowTitle("ARTIQ Browser")

        qfm = QtGui.QFontMetrics(self.font())
        self.resize(140*qfm.averageCharWidth(), 38*qfm.lineSpacing())

        self.exit_request = asyncio.Event()

        self.setUnifiedTitleAndToolBarOnMac(True)

        self.experiments = experiments.ExperimentsArea(
            browse_root, datasets_sub)
        self.experiments.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self.experiments.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self.setCentralWidget(self.experiments)

        self.files = files.FilesDock(datasets_sub, browse_root, select=select)

        self.files.dataset_activated.connect(
            self.experiments.dataset_activated)
        self.files.dataset_changed.connect(
            self.experiments.dataset_changed)

        self.applets = applets.AppletsDock(self, datasets_sub)
        atexit_register_coroutine(self.applets.stop)

        self.datasets = datasets.DatasetsDock(datasets_sub)

        self.log = log.LogDock(None, "log")
        self.log.setFeatures(self.log.DockWidgetMovable |
                             self.log.DockWidgetFloatable)

        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.files)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.applets)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.datasets)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.log)

        g = self.menuBar().addMenu("&Experiment")
        a = QtWidgets.QAction("&Open", self)
        a.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_DialogOpenButton))
        a.setShortcuts(QtGui.QKeySequence.Open)
        a.setStatusTip("Open an experiment")
        a.triggered.connect(self.experiments.select_experiment)
        g.addAction(a)

        g = self.menuBar().addMenu("&View")
        a = QtWidgets.QAction("Cascade", self)
        a.setStatusTip("Cascade experiment windows")
        a.triggered.connect(self.experiments.cascadeSubWindows)
        g.addAction(a)
        a = QtWidgets.QAction("Tile", self)
        a.setStatusTip("Tile experiment windows")
        a.triggered.connect(self.experiments.tileSubWindows)
        g.addAction(a)

    def closeEvent(self, event):
        event.ignore()
        self.exit_request.set()

    def save_state(self):
        return {
            "geometry": bytes(self.saveGeometry()),
            "state": bytes(self.saveState()),
            "experiments": self.experiments.save_state(),
            "files": self.files.save_state(),
            "datasets": self.datasets.save_state(),
            "log": self.log.save_state(),
            "applets": self.applets.save_state(),
        }

    def restore_state(self, state):
        self.applets.restore_state(state["applets"])
        self.log.restore_state(state["log"])
        self.datasets.restore_state(state["datasets"])
        self.files.restore_state(state["files"])
        self.experiments.restore_state(state["experiments"])
        self.restoreState(QtCore.QByteArray(state["state"]))
        self.restoreGeometry(QtCore.QByteArray(state["geometry"]))


def main():
    # initialize application
    args = get_argparser().parse_args()
    widget_log_handler = log.init_log(args, "browser")

    app = QtWidgets.QApplication(["ARTIQ Browser"])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)

    datasets_sub = models.LocalModelManager(datasets.Model)
    datasets_sub.init({})

    smgr = state.StateManager(args.db_file)

    main_window = Browser(datasets_sub, args.browse_root, args.select)
    widget_log_handler.callback = main_window.log.append_message
    smgr.register(main_window)

    if os.name == "nt":
        # HACK: show the main window before creating applets.
        # Otherwise, the windows of those applets that are in detached
        # QDockWidgets fail to be embedded.
        main_window.show()
    smgr.load()
    smgr.start()
    atexit_register_coroutine(smgr.stop)
    main_window.show()
    loop.run_until_complete(main_window.exit_request.wait())


if __name__ == "__main__":
    main()
