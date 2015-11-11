#!/usr/bin/env python3.5

import argparse
import asyncio
import atexit
import os

# Quamash must be imported first so that pyqtgraph picks up the Qt binding
# it has chosen.
from quamash import QEventLoop, QtGui, QtCore
from pyqtgraph import dockarea

from artiq.tools import verbosity_args, init_logger, artiq_dir
from artiq.protocols.pc_rpc import AsyncioClient
from artiq.gui.models import ModelSubscriber
from artiq.gui import state, explorer, moninj, datasets, schedule, log, console


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


class MainWindow(QtGui.QMainWindow):
    def __init__(self, app, server):
        QtGui.QMainWindow.__init__(self)
        icon = QtGui.QIcon(os.path.join(artiq_dir, "gui", "icon.png"))
        self.setWindowIcon(icon)
        self.setWindowTitle("ARTIQ - {}".format(server))
        self.exit_request = asyncio.Event()

    def closeEvent(self, *args):
        self.exit_request.set()

    def save_state(self):
        return bytes(self.saveGeometry())

    def restore_state(self, state):
        self.restoreGeometry(QtCore.QByteArray(state))


def atexit_register_coroutine(coroutine, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.run_until_complete(coroutine()))


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    app = QtGui.QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)

    rpc_clients = dict()
    for target in "schedule", "repository", "dataset_db":
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

    smgr = state.StateManager(args.db_file)

    win = MainWindow(app, args.server)
    area = dockarea.DockArea()
    smgr.register(area)
    smgr.register(win)
    win.setCentralWidget(area)
    status_bar = QtGui.QStatusBar()
    status_bar.showMessage("Connected to {}".format(args.server))
    win.setStatusBar(status_bar)

    d_explorer = explorer.ExplorerDock(win, status_bar,
                                       sub_clients["explist"],
                                       sub_clients["schedule"],
                                       rpc_clients["schedule"],
                                       rpc_clients["repository"])
    smgr.register(d_explorer)

    d_datasets = datasets.DatasetsDock(win, area, sub_clients["datasets"])
    smgr.register(d_datasets)

    if os.name != "nt":
        d_ttl_dds = moninj.MonInj()
        loop.run_until_complete(d_ttl_dds.start(args.server, args.port_notify))
        atexit_register_coroutine(d_ttl_dds.stop)

    if os.name != "nt":
        area.addDock(d_ttl_dds.dds_dock, "top")
        area.addDock(d_ttl_dds.ttl_dock, "above", d_ttl_dds.dds_dock)
        area.addDock(d_datasets, "above", d_ttl_dds.ttl_dock)
    else:
        area.addDock(d_datasets, "top")
    area.addDock(d_explorer, "above", d_datasets)

    d_schedule = schedule.ScheduleDock(
        status_bar, rpc_clients["schedule"], sub_clients["schedule"])

    d_log = log.LogDock(sub_clients["log"])
    smgr.register(d_log)

    def _set_dataset(k, v):
        asyncio.ensure_future(rpc_clients["dataset_db"].set(k, v))
    def _del_dataset(k):
        asyncio.ensure_future(rpc_clients["dataset_db"].delete(k))
    d_console = console.ConsoleDock(
        d_datasets.get_dataset,
        _set_dataset,
        _del_dataset)

    area.addDock(d_console, "bottom")
    area.addDock(d_log, "above", d_console)
    area.addDock(d_schedule, "above", d_log)

    smgr.load()
    smgr.start()
    atexit_register_coroutine(smgr.stop)
    win.show()
    loop.run_until_complete(win.exit_request.wait())

if __name__ == "__main__":
    main()
