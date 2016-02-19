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
from artiq.gui import (state, experiments, shortcuts, explorer,
                       moninj, datasets, applets, schedule, log)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ GUI client")
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
        "--db-file", default="artiq_gui.pyon",
        help="database file for local GUI settings")
    verbosity_args(parser)
    return parser


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, server):
        QtWidgets.QMainWindow.__init__(self)
        icon = QtGui.QIcon(os.path.join(artiq_dir, "gui", "icon.png"))
        self.setWindowIcon(icon)
        self.setWindowTitle("ARTIQ - {}".format(server))
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


def main():
    # initialize application
    args = get_argparser().parse_args()
    init_logger(args)

    app = QtWidgets.QApplication([])
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
    for notifier_name, module in (("explist", explorer),
                                  ("datasets", datasets),
                                  ("schedule", schedule),
                                  ("log", log)):
        subscriber = ModelSubscriber(notifier_name, module.Model)
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
    mdi_area = QtWidgets.QMdiArea()
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
                                       rpc_clients["schedule"],
                                       rpc_clients["experiment_db"])

    d_datasets = datasets.DatasetsDock(sub_clients["datasets"],
                                       rpc_clients["dataset_db"])

    d_applets = applets.AppletsDock(main_window, sub_clients["datasets"])
    atexit_register_coroutine(d_applets.stop)
    smgr.register(d_applets)

    if os.name != "nt":
        d_ttl_dds = moninj.MonInj()
        loop.run_until_complete(d_ttl_dds.start(args.server, args.port_notify))
        atexit_register_coroutine(d_ttl_dds.stop)

    d_schedule = schedule.ScheduleDock(
        status_bar, rpc_clients["schedule"], sub_clients["schedule"])

    logmgr = log.LogDockManager(main_window, sub_clients["log"])
    smgr.register(logmgr)

    # lay out docks
    if os.name != "nt":
        main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, d_ttl_dds.dds_dock)
        main_window.tabifyDockWidget(d_ttl_dds.dds_dock, d_ttl_dds.ttl_dock)
        main_window.tabifyDockWidget(d_ttl_dds.ttl_dock, d_applets)
        main_window.tabifyDockWidget(d_applets, d_datasets)
    else:
        main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, d_applets)
        main_window.tabifyDockWidget(d_applets, d_datasets)
    main_window.tabifyDockWidget(d_datasets, d_shortcuts)
    main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, d_schedule)
    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, d_explorer)

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
        main_window.tabifyDockWidget(d_shortcuts, d_log0)

    # run
    main_window.show()
    loop.run_until_complete(main_window.exit_request.wait())

if __name__ == "__main__":
    main()
