import logging
import asyncio
import sys
import shlex
from functools import partial

from quamash import QtCore, QtGui, QtWidgets
from pyqtgraph import dockarea


logger = logging.getLogger(__name__)


class AppletDock(dockarea.Dock):
    def __init__(self, token, name, command):
        dockarea.Dock.__init__(self, "applet" + str(token),
                               label="Applet: " + name,
                               closable=True)
        self.setMinimumSize(QtCore.QSize(500, 400))
        self.token = token
        self.applet_name = name
        self.command = command

    def rename(self, name):
        self.applet_name = name
        self.label.setText("Applet: " + name)

    async def start(self):
        command = self.command.format(python=sys.executable,
                                      embed_token=self.token)
        logger.debug("starting command %s for %s", command, self.applet_name)
        try:
            self.process = await asyncio.create_subprocess_exec(
                                *shlex.split(command))
        except:
            logger.warning("Applet %s failed to start", self.applet_name,
                           exc_info=True)

    def capture(self, win_id):
        logger.debug("capturing window 0x%x for %s", win_id, self.applet_name)
        self.captured_window = QtGui.QWindow.fromWinId(win_id)
        self.captured_widget = QtWidgets.QWidget.createWindowContainer(
            self.captured_window)
        self.addWidget(self.captured_widget)

    async def terminate(self):
        if hasattr(self, "captured_window"):
            self.captured_window.close()
            self.captured_widget.deleteLater()
            del self.captured_window
            del self.captured_widget
        if hasattr(self, "process"):
            try:
                await asyncio.wait_for(self.process.wait(), 2.0)
            except:
                logger.warning("Applet %s failed to exit, killing",
                               self.applet_name)
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
                await self.process.wait()
            del self.process

    async def restart(self):
        await self.terminate()
        await self.start()


_templates = [
    ("Big number", "{python} -m artiq.applets.big_number "
                   "--embed {embed_token} NUMBER_DATASET"),
    ("Histogram", "{python} -m artiq.applets.plot_hist "
                  "--embed {embed_token} COUNTS_DATASET "
                  "--x BIN_BOUNDARIES_DATASET"),
    ("XY", "{python} -m artiq.applets.plot_xy "
           "--embed {embed_token} Y_DATASET --x X_DATASET "
           "--error ERROR_DATASET --fit FIT_DATASET"),
    ("XY + Histogram", "{python} -m artiq.applets.plot_xy_hist "
                       "--embed {embed_token} X_DATASET "
                       "HIST_BIN_BOUNDARIES_DATASET "
                       "HISTS_COUNTS_DATASET"),
]


class AppletsDock(dockarea.Dock):
    def __init__(self, manager):
        self.manager = manager
        self.token_to_checkbox = dict()

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
        restart_action.triggered.connect(self.restart)
        self.table.addAction(restart_action)
        delete_action = QtGui.QAction("Delete selected applet", self.table)
        delete_action.triggered.connect(self.delete)
        self.table.addAction(delete_action)

        self.table.cellChanged.connect(self.cell_changed)

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
                    token = self.manager.create(name, command)
                    item.applet_token = token
                    self.token_to_checkbox[token] = item
            else:
                token = getattr(item, "applet_token", None)
                if token is not None:
                    # cell_changed is emitted at row creation
                    self.manager.delete(token)
        elif column == 1 or column == 2:
            new_value = self.table.item(row, column).text()
            token = getattr(self.table.item(row, 0), "applet_token", None)
            if token is not None:
                if column == 1:
                    self.manager.rename(token, new_value)
                else:
                    self.manager.set_command(token, new_value)

    def disable_token(self, token):
        checkbox_item = self.token_to_checkbox[token]
        checkbox_item.applet_token = None
        del self.token_to_checkbox[token]
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
            token = getattr(self.table.item(row, 0), "applet_token", None)
            if token is not None:
                asyncio.ensure_future(self.manager.restart(token))

    def delete(self):
        selection = self.table.selectedRanges()
        if selection:
            row = selection[0].topRow()
            token = getattr(self.table.item(row, 0), "applet_token", None)
            if token is not None:
                self.manager.delete(token)
            self.table.removeRow(row)

    def save_state(self):
        state = []
        for row in range(self.table.rowCount()):
            enabled = self.table.item(row, 0).checkState() == QtCore.Qt.Checked
            name = self.table.item(row, 1).text()
            command = self.table.item(row, 2).text()
            state.append((enabled, name, command))
        return state

    def restore_state(self, state):
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


class AppletManagerRPC:
    def __init__(self, parent):
        self.parent = parent

    def embed(self, token, win_id):
        self.parent.embed(token, win_id)


class AppletManager:
    def __init__(self, dock_area):
        self.dock_area = dock_area
        self.main_dock = AppletsDock(self)
        self.rpc = AppletManagerRPC(self)
        self.applet_docks = dict()
        self.workaround_pyqtgraph_bug = False

    def embed(self, token, win_id):
        if token not in self.applet_docks:
            logger.warning("Ignored incorrect embed token %d for winid 0x%x",
                            token, win_id)
            return
        self.applet_docks[token].capture(win_id)

    def create(self, name, command):
        token = next(iter(set(range(len(self.applet_docks) + 1))
                          - self.applet_docks.keys()))
        dock = AppletDock(token, name, command)
        self.applet_docks[token] = dock
        # If a dock is floated and then dock state is restored, pyqtgraph
        # leaves a "phantom" window open.
        if self.workaround_pyqtgraph_bug:
            self.dock_area.addDock(dock)
        else:
            self.dock_area.floatDock(dock)
        asyncio.ensure_future(dock.start())
        dock.sigClosed.connect(partial(self.on_dock_closed, token))
        return token

    def on_dock_closed(self, token):
        asyncio.ensure_future(self.applet_docks[token].terminate())
        self.main_dock.disable_token(token)
        del self.applet_docks[token]

    def delete(self, token):
        # This in turns calls on_dock_closed and main_dock.disable_token
        self.applet_docks[token].close()

    def rename(self, token, name):
        self.applet_docks[token].rename(name)

    def set_command(self, token, command):
        self.applet_docks[token].command = command

    async def restart(self, token):
        await self.applet_docks[token].restart()

    async def stop(self):
        for dock in self.applet_docks.values():
            await dock.terminate()

    def save_state(self):
        return self.main_dock.save_state()

    def restore_state(self, state):
        self.workaround_pyqtgraph_bug = True
        self.main_dock.restore_state(state)
        self.workaround_pyqtgraph_bug = False
