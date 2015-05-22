#!/usr/bin/env python3

import argparse
import asyncio
import atexit

# Quamash must be imported first so that pyqtgraph picks up the Qt binding
# it has chosen.
from quamash import QEventLoop, QtGui
from pyqtgraph.dockarea import DockArea

from artiq.protocols.file_db import FlatFileDB
from artiq.gui.schedule import ScheduleDock
from artiq.gui.parameters import ParametersDock


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

    win = QtGui.QMainWindow()
    area = DockArea()
    win.setCentralWidget(area)
    win.resize(1000, 500)
    win.setWindowTitle("ARTIQ")

    d_params = ParametersDock(area)
    area.addDock(d_params, "left")
    loop.run_until_complete(d_params.sub_connect(
        args.server, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(d_params.sub_close()))

    d_schedule = ScheduleDock(area)
    area.addDock(d_schedule, "top", d_params)
    loop.run_until_complete(d_schedule.sub_connect(
        args.server, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(d_schedule.sub_close()))

    win.show()
    loop.run_forever()

if __name__ == "__main__":
    main()
