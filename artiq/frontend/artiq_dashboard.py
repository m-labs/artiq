#!/usr/bin/env python3.5

import argparse
import asyncio
import atexit
import os

from PyQt5 import QtCore, QtGui, QtWidgets
from quamash import QEventLoop

from artiq import __artiq_dir__ as artiq_dir
from artiq.tools import *
from artiq.protocols.pc_rpc import AsyncioClient
from artiq.gui.models import ModelSubscriber
from artiq.gui import state, applets, log
from artiq.dashboard import (experiments, shortcuts, explorer,
                             moninj, datasets, schedule)


def get_argparser():
    if os.name == "nt":
        default_db_file = os.path.expanduser("~\\artiq_dashboard.pyon")
    else:
        default_db_file = os.path.expanduser("~/.artiq_dashboard.pyon")

    parser = argparse.ArgumentParser(description="ARTIQ Dashboard")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port-notify", default=3250, type=int,
        help="TCP port to connect to for notifications")
    parser.add_argument(
        "--port-control", default=3251, type=int,
        help="TCP port to connect to for control")
    parser.add_argument(
        "--db-file", default=default_db_file,
        help="database file for local GUI settings "
             "(default: %(default)s)")
    verbosity_args(parser)
    return parser


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, server):
        QtWidgets.QMainWindow.__init__(self)

        icon = QtGui.QIcon(os.path.join(artiq_dir, "gui", "logo.svg"))
        self.setWindowIcon(icon)
        self.setWindowTitle("ARTIQ Dashboard - {}".format(server))

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
        self.pixmap = QtGui.QPixmap(os.path.join(artiq_dir, "gui", "logo20.svg"))

    def paintEvent(self, event):
        QtWidgets.QMdiArea.paintEvent(self, event)
        painter = QtGui.QPainter(self.viewport())
        x = (self.width() - self.pixmap.width())//2
        y = (self.height() - self.pixmap.height())//2
        painter.setOpacity(0.5)
        painter.drawPixmap(x, y, self.pixmap)


def main():
    # initialize application
    args = get_argparser().parse_args()
    init_logger(args)

    app = QtWidgets.QApplication(["ARTIQ Dashboard"])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)
    smgr = state.StateManager(args.db_file)

    # create connections to master
    rpc_clients = dict()
    for target in "schedule", "experiment_db", "dataset_db":
        client = AsyncioClient()
        loop.run_until_complete(client.connect_rpc(
            args.server, args.port_control, "master_" + target))
        atexit.register(client.close_rpc)
        rpc_clients[target] = client

    sub_clients = dict()
    for notifier_name, modelf in (("explist", explorer.Model),
                                  ("explist_status", explorer.StatusUpdater),
                                  ("datasets", datasets.Model),
                                  ("schedule", schedule.Model),
                                  ("log", log.Model)):
        subscriber = ModelSubscriber(notifier_name, modelf)
        loop.run_until_complete(subscriber.connect(
            args.server, args.port_notify))
        atexit_register_coroutine(subscriber.close)
        sub_clients[notifier_name] = subscriber

    # initialize main window
    main_window = MainWindow(args.server)
    smgr.register(main_window)
    status_bar = QtWidgets.QStatusBar()
    status_bar.showMessage("Connected to {}".format(args.server))
    main_window.setStatusBar(status_bar)
    mdi_area = MdiArea()
    mdi_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    mdi_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    main_window.setCentralWidget(mdi_area)

    # create UI components
    expmgr = experiments.ExperimentManager(main_window,
                                           sub_clients["explist"],
                                           sub_clients["schedule"],
                                           rpc_clients["schedule"],
                                           rpc_clients["experiment_db"])
    smgr.register(expmgr)
    d_shortcuts = shortcuts.ShortcutsDock(main_window, expmgr)
    smgr.register(d_shortcuts)
    d_explorer = explorer.ExplorerDock(status_bar, expmgr, d_shortcuts,
                                       sub_clients["explist"],
                                       sub_clients["explist_status"],
                                       rpc_clients["schedule"],
                                       rpc_clients["experiment_db"])

    d_datasets = datasets.DatasetsDock(sub_clients["datasets"],
                                       rpc_clients["dataset_db"])
    smgr.register(d_datasets)

    d_applets = applets.AppletsDock(main_window, sub_clients["datasets"])
    atexit_register_coroutine(d_applets.stop)
    smgr.register(d_applets)

    d_ttl_dds = moninj.MonInj()
    loop.run_until_complete(d_ttl_dds.start(args.server, args.port_notify))
    atexit_register_coroutine(d_ttl_dds.stop)

    d_schedule = schedule.ScheduleDock(
        status_bar, rpc_clients["schedule"], sub_clients["schedule"])
    smgr.register(d_schedule)

    logmgr = log.LogDockManager(main_window, sub_clients["log"])
    smgr.register(logmgr)

    # lay out docks
    right_docks = [
        d_explorer, d_shortcuts,
        d_ttl_dds.ttl_dock, d_ttl_dds.dds_dock,
        d_datasets, d_applets
    ]
    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, right_docks[0])
    for d1, d2 in zip(right_docks, right_docks[1:]):
        main_window.tabifyDockWidget(d1, d2)
    main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, d_schedule)

    # load/initialize state
    if os.name == "nt":
        # HACK: show the main window before creating applets.
        # Otherwise, the windows of those applets that are in detached
        # QDockWidgets fail to be embedded.
        main_window.show()
    smgr.load()
    smgr.start()
    atexit_register_coroutine(smgr.stop)

    # create first log dock if not already in state
    d_log0 = logmgr.first_log_dock()
    if d_log0 is not None:
        main_window.tabifyDockWidget(d_schedule, d_log0)

    # run
    main_window.show()
    loop.run_until_complete(main_window.exit_request.wait())

if __name__ == "__main__":
    main()
