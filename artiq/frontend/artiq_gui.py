#!/usr/bin/env python3

import argparse
import asyncio
import atexit

# Quamash must be imported first so that pyqtgraph picks up the Qt binding
# it has chosen.
from quamash import QEventLoop, QtGui
from pyqtgraph import dockarea
import os

from artiq.protocols.file_db import FlatFileDB
from artiq.protocols.pc_rpc import AsyncioClient
from artiq.gui.explorer import ExplorerDock
from artiq.gui.moninj import MonInj
from artiq.gui.parameters import ParametersDock
from artiq.gui.schedule import ScheduleDock
from artiq.gui.log import LogDock

data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                        "..", "gui")

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
    return parser


def main():
    args = get_argparser().parse_args()

    db = FlatFileDB(args.db_file, default_data=dict())

    app = QtGui.QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    atexit.register(lambda: loop.close())

    schedule_ctl = AsyncioClient()
    loop.run_until_complete(schedule_ctl.connect_rpc(
        args.server, args.port_control, "master_schedule"))
    atexit.register(lambda: schedule_ctl.close_rpc())

    win = QtGui.QMainWindow()
    win.setWindowIcon(QtGui.QIcon(os.path.join(data_dir, "icon.png")))
    area = dockarea.DockArea()
    win.setCentralWidget(area)
    status_bar = QtGui.QStatusBar()
    status_bar.showMessage("Connected to {}".format(args.server))
    win.setStatusBar(status_bar)
    win.resize(1400, 800)
    win.setWindowTitle("ARTIQ")

    d_explorer = ExplorerDock(status_bar, schedule_ctl)
    loop.run_until_complete(d_explorer.sub_connect(
        args.server, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(d_explorer.sub_close()))

    d_ttl_dds = MonInj()
    loop.run_until_complete(d_ttl_dds.start(args.server, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(d_ttl_dds.stop()))
    area.addDock(d_ttl_dds.dds_dock, "top")
    area.addDock(d_ttl_dds.ttl_dock, "above", d_ttl_dds.dds_dock)
    area.addDock(d_explorer, "above", d_ttl_dds.ttl_dock)

    d_params = ParametersDock()
    area.addDock(d_params, "right", d_explorer)
    loop.run_until_complete(d_params.sub_connect(
        args.server, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(d_params.sub_close()))

    d_schedule = ScheduleDock(schedule_ctl)
    loop.run_until_complete(d_schedule.sub_connect(
        args.server, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(d_schedule.sub_close()))

    d_log = LogDock()

    area.addDock(d_log, "bottom")
    area.addDock(d_schedule, "above", d_log)

    win.show()
    loop.run_forever()

if __name__ == "__main__":
    main()
