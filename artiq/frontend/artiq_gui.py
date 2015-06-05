#!/usr/bin/env python3

import argparse
import asyncio
import atexit

# Quamash must be imported first so that pyqtgraph picks up the Qt binding
# it has chosen.
from quamash import QEventLoop, QtGui
from pyqtgraph import dockarea

from artiq.protocols.file_db import FlatFileDB
from artiq.protocols.pc_rpc import AsyncioClient
from artiq.protocols.sync_struct import Subscriber
from artiq.gui.explorer import ExplorerDock
from artiq.gui.moninj import MonInjTTLDock, MonInjDDSDock
from artiq.gui.parameters import ParametersDock
from artiq.gui.schedule import ScheduleDock
from artiq.gui.log import LogDock


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

    d_ttl = MonInjTTLDock()
    loop.run_until_complete(d_ttl.start())
    atexit.register(lambda: loop.run_until_complete(d_ttl.stop()))
    d_dds = MonInjDDSDock()
    devices_sub = Subscriber("devices",
                             [d_ttl.init_devices, d_dds.init_devices])
    loop.run_until_complete(
        devices_sub.connect(args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(devices_sub.close()))

    area.addDock(d_dds, "top")
    area.addDock(d_ttl, "above", d_dds)
    area.addDock(d_explorer, "above", d_ttl)

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
