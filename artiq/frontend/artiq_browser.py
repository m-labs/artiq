#!/usr/bin/env python3

import argparse
import asyncio
import atexit
import os
import logging

from PyQt5 import QtCore, QtGui, QtWidgets
from quamash import QEventLoop

from sipyco.asyncio_tools import atexit_register_coroutine
from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq import __artiq_dir__ as artiq_dir
from artiq.tools import get_user_config_dir
from artiq.gui import state, applets, models, log
from artiq.browser import datasets, files, experiments


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ Browser")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")
    parser.add_argument("--db-file", default=None,
                        help="database file for local browser settings "
                        "(default: %(default)s)")
    parser.add_argument("--browse-root", default="",
                        help="root path for directory tree "
                        "(default %(default)s)")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to "
             "when uploading datasets")
    parser.add_argument(
        "--port", default=3251, type=int,
        help="TCP port to use to connect to the master")
    parser.add_argument("select", metavar="SELECT", nargs="?",
                        help="directory to browse or file to load")
    common_args.verbosity_args(parser)
    return parser


class Browser(QtWidgets.QMainWindow):
    def __init__(self, smgr, datasets_sub, browse_root,
                 master_host, master_port):
        QtWidgets.QMainWindow.__init__(self)
        smgr.register(self)

        icon = QtGui.QIcon(os.path.join(artiq_dir, "gui", "logo.svg"))
        self.setWindowIcon(icon)
        self.setWindowTitle("ARTIQ Browser")

        qfm = QtGui.QFontMetrics(self.font())
        self.resize(140*qfm.averageCharWidth(), 38*qfm.lineSpacing())

        self.exit_request = asyncio.Event()

        self.setUnifiedTitleAndToolBarOnMac(True)

        self.experiments = experiments.ExperimentsArea(
            browse_root, datasets_sub)
        smgr.register(self.experiments)
        self.experiments.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self.experiments.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self.setCentralWidget(self.experiments)

        self.files = files.FilesDock(datasets_sub, browse_root)
        smgr.register(self.files)

        self.files.dataset_activated.connect(
            self.experiments.dataset_activated)
        self.files.dataset_changed.connect(
            self.experiments.dataset_changed)

        self.applets = applets.AppletsDock(self, datasets_sub)
        smgr.register(self.applets)
        atexit_register_coroutine(self.applets.stop)

        self.datasets = datasets.DatasetsDock(
            datasets_sub, master_host, master_port)
        smgr.register(self.datasets)
        self.files.metadata_changed.connect(self.datasets.metadata_changed)

        self.log = log.LogDock(None, "log")
        smgr.register(self.log)
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
        }

    def restore_state(self, state):
        self.restoreState(QtCore.QByteArray(state["state"]))
        self.restoreGeometry(QtCore.QByteArray(state["geometry"]))


def main():
    # initialize application
    args = get_argparser().parse_args()
    if args.db_file is None:
        args.db_file = os.path.join(get_user_config_dir(), "artiq_browser.pyon")
    widget_log_handler = log.init_log(args, "browser")

    app = QtWidgets.QApplication(["ARTIQ Browser"])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)

    datasets_sub = models.LocalModelManager(datasets.Model)
    datasets_sub.init({})

    smgr = state.StateManager(args.db_file)

    browser = Browser(smgr, datasets_sub, args.browse_root,
                      args.server, args.port)
    widget_log_handler.callback = browser.log.append_message

    if os.name == "nt":
        # HACK: show the main window before creating applets.
        # Otherwise, the windows of those applets that are in detached
        # QDockWidgets fail to be embedded.
        browser.show()
    smgr.load()
    smgr.start()
    atexit_register_coroutine(smgr.stop)

    if args.select is not None:
        browser.files.select(args.select)

    browser.show()
    loop.run_until_complete(browser.exit_request.wait())


if __name__ == "__main__":
    main()
