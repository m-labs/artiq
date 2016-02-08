import logging
import asyncio
import sys
import shlex
from functools import partial

from quamash import QtCore, QtGui, QtWidgets
from pyqtgraph import dockarea

from artiq.protocols import pyon
from artiq.protocols.pipe_ipc import AsyncioParentComm


logger = logging.getLogger(__name__)


class AppletIPCServer(AsyncioParentComm):
    def __init__(self, capture_cb):
        AsyncioParentComm.__init__(self)
        self.capture_cb = capture_cb

    def write_pyon(self, obj):
        self.write(pyon.encode(obj).encode() + b"\n")

    async def read_pyon(self):
        line = await self.readline()
        return pyon.decode(line.decode())

    async def serve(self):
        while True:
            obj = await self.read_pyon()
            try:
                action = obj["action"]
                if action == "embed":
                    self.capture_cb(obj["win_id"])
                    self.write_pyon({"action": "embed_done"})
                else:
                    raise ValueError("unknown action in applet request")
            except:
                logger.warning("error processing applet request",
                               exc_info=True)
                self.write_pyon({"action": "error"})


class AppletDock(dockarea.Dock):
    def __init__(self, name, command):
        dockarea.Dock.__init__(self, "applet" + str(id(self)), # XXX
                               label="Applet: " + name,
                               closable=True)
        self.setMinimumSize(QtCore.QSize(500, 400))
        self.applet_name = name
        self.command = command

    def rename(self, name):
        self.applet_name = name
        self.label.setText("Applet: " + name)

    async def start(self):
        self.ipc = AppletIPCServer(self.capture)
        command = self.command.format(python=sys.executable,
                                      ipc_address=self.ipc.get_address())
        logger.debug("starting command %s for %s", command, self.applet_name)
        try:
            await self.ipc.create_subprocess(*shlex.split(command))
        except:
            logger.warning("Applet %s failed to start", self.applet_name,
                           exc_info=True)
        asyncio.ensure_future(self.ipc.serve())

    def capture(self, win_id):
        logger.debug("capturing window 0x%x for %s", win_id, self.applet_name)
        captured_window = QtGui.QWindow.fromWinId(win_id)
        captured_widget = QtWidgets.QWidget.createWindowContainer(
            captured_window)
        self.addWidget(captured_widget)

    async def terminate(self):
        if hasattr(self, "process"):
            # TODO: send IPC termination request
            try:
                await asyncio.wait_for(self.ipc.process.wait(), 2.0)
            except:
                logger.warning("Applet %s failed to exit, killing",
                               self.applet_name)
                try:
                    self.ipc.process.kill()
                except ProcessLookupError:
                    pass
                await self.ipc.process.wait()
            del self.ipc

    async def restart(self):
        await self.terminate()
        await self.start()


_templates = [
    ("Big number", "{python} -m artiq.applets.big_number "
                   "embedded {ipc_address} NUMBER_DATASET"),
    ("Histogram", "{python} -m artiq.applets.plot_hist "
                  "embedded {ipc_address} COUNTS_DATASET "
                  "--x BIN_BOUNDARIES_DATASET"),
    ("XY", "{python} -m artiq.applets.plot_xy "
           "embedded {ipc_address} Y_DATASET --x X_DATASET "
           "--error ERROR_DATASET --fit FIT_DATASET"),
    ("XY + Histogram", "{python} -m artiq.applets.plot_xy_hist "
                       "embedded {ipc_address} X_DATASET "
                       "HIST_BIN_BOUNDARIES_DATASET "
                       "HISTS_COUNTS_DATASET"),
]


class AppletsDock(dockarea.Dock):
    def __init__(self, dock_area):
        self.dock_area = dock_area
        self.dock_to_checkbox = dict()
        self.workaround_pyqtgraph_bug = False

        dockarea.Dock.__init__(self, "Applets")
        self.setMinimumSize(QtCore.QSize(850, 450))

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Enable", "Name", "Command"])
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setTextElideMode(QtCore.Qt.ElideNone)
        self.addWidget(self.table)

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        new_action = QtGui.QAction("New applet", self.table)
        new_action.triggered.connect(self.new)
        self.table.addAction(new_action)
        templates_menu = QtGui.QMenu()
        for name, template in _templates:
            action = QtGui.QAction(name, self.table)
            action.triggered.connect(partial(self.new_template, template))
            templates_menu.addAction(action)
        restart_action = QtGui.QAction("New applet from template", self.table)
        restart_action.setMenu(templates_menu)
        self.table.addAction(restart_action)
        restart_action = QtGui.QAction("Restart selected applet", self.table)
        restart_action.setShortcut("CTRL+R")
        restart_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        restart_action.triggered.connect(self.restart)
        self.table.addAction(restart_action)
        delete_action = QtGui.QAction("Delete selected applet", self.table)
        delete_action.setShortcut("DELETE")
        delete_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        delete_action.triggered.connect(self.delete)
        self.table.addAction(delete_action)

        self.table.cellChanged.connect(self.cell_changed)

    def create(self, name, command):
        dock = AppletDock(name, command)
        # If a dock is floated and then dock state is restored, pyqtgraph
        # leaves a "phantom" window open.
        if self.workaround_pyqtgraph_bug:
            self.dock_area.addDock(dock)
        else:
            self.dock_area.floatDock(dock)
        asyncio.ensure_future(dock.start())
        dock.sigClosed.connect(partial(self.on_dock_closed, dock))
        return dock

    def cell_changed(self, row, column):
        if column == 0:
            item = self.table.item(row, column)
            if item.checkState() == QtCore.Qt.Checked:
                command = self.table.item(row, 2)
                if command:
                    command = command.text()
                    name = self.table.item(row, 1)
                    if name is None:
                        name = ""
                    else:
                        name = name.text()
                    dock = self.create(name, command)
                    item.applet_dock = dock
                    self.dock_to_checkbox[dock] = item
            else:
                dock = getattr(item, "applet_dock", None)
                if dock is not None:
                    # This calls self.on_dock_closed
                    dock.close()
        elif column == 1 or column == 2:
            new_value = self.table.item(row, column).text()
            dock = getattr(self.table.item(row, 0), "applet_dock", None)
            if dock is not None:
                if column == 1:
                    dock.rename(new_value)
                else:
                    dock.command = new_value

    def on_dock_closed(self, dock):
        asyncio.ensure_future(dock.terminate())
        checkbox_item = self.dock_to_checkbox[dock]
        checkbox_item.applet_dock = None
        del self.dock_to_checkbox[dock]
        checkbox_item.setCheckState(QtCore.Qt.Unchecked)

    def new(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        checkbox = QtWidgets.QTableWidgetItem()
        checkbox.setFlags(QtCore.Qt.ItemIsSelectable |
                          QtCore.Qt.ItemIsUserCheckable |
                          QtCore.Qt.ItemIsEnabled)
        checkbox.setCheckState(QtCore.Qt.Unchecked)
        self.table.setItem(row, 0, checkbox)
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem())
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem())
        return row

    def new_template(self, template):
        row = self.new()
        self.table.item(row, 2).setText(template)

    def restart(self):
        selection = self.table.selectedRanges()
        if selection:
            row = selection[0].topRow()
            dock = getattr(self.table.item(row, 0), "applet_dock", None)
            if dock is not None:
                asyncio.ensure_future(dock.restart())

    def delete(self):
        selection = self.table.selectedRanges()
        if selection:
            row = selection[0].topRow()
            dock = getattr(self.table.item(row, 0), "applet_dock", None)
            if dock is not None:
                # This calls self.on_dock_closed
                dock.close()
            self.table.removeRow(row)

    async def stop(self):
        for row in range(self.table.rowCount()):
            dock = getattr(self.table.item(row, 0), "applet_dock", None)
            if dock is not None:
                await dock.terminate()

    def save_state(self):
        state = []
        for row in range(self.table.rowCount()):
            enabled = self.table.item(row, 0).checkState() == QtCore.Qt.Checked
            name = self.table.item(row, 1).text()
            command = self.table.item(row, 2).text()
            state.append((enabled, name, command))
        return state

    def restore_state(self, state):
        self.workaround_pyqtgraph_bug = True
        for enabled, name, command in state:
            row = self.new()
            item = QtWidgets.QTableWidgetItem()
            item.setText(name)
            self.table.setItem(row, 1, item)
            item = QtWidgets.QTableWidgetItem()
            item.setText(command)
            self.table.setItem(row, 2, item)
            if enabled:
                self.table.item(row, 0).setCheckState(QtCore.Qt.Checked)
        self.workaround_pyqtgraph_bug = False
