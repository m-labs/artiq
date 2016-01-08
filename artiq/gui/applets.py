import logging
import asyncio
import shlex

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

    async def start(self):
        command = self.command.format(embed_token=self.token)
        logger.debug("starting command %s for %s", command, self.applet_name)
        try:
            self.process = await asyncio.create_subprocess_exec(
                                *shlex.split(command))
        except FileNotFoundError:
            logger.warning("Applet %s failed to start", self.applet_name)
        else:
            logger.warning("Applet %s exited", self.applet_name)

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


class AppletsDock(dockarea.Dock):
    def __init__(self, manager):
        self.manager = manager

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
        restart_action = QtGui.QAction("Restart selected applet", self.table)
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
            else:
                token = getattr(item, "applet_token", None)
                if token is not None:
                    # cell_changed is emitted at row creation
                    self.manager.delete(token)
                    item.applet_token = None

    def new(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        checkbox = QtWidgets.QTableWidgetItem()
        checkbox.setFlags(QtCore.Qt.ItemIsSelectable |
                          QtCore.Qt.ItemIsUserCheckable |
                          QtCore.Qt.ItemIsEnabled)
        checkbox.setCheckState(QtCore.Qt.Unchecked)
        self.table.setItem(row, 0, checkbox)

    def delete(self):
        selection = self.table.selectedRanges()
        if selection:
            self.table.deleteRow(selection[0].topRow())


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
        self.dock_area.floatDock(dock)
        asyncio.ensure_future(dock.start())
        return token

    def delete(self, token):
        del self.applet_docks[token]

    async def stop(self):
        for dock in self.applet_docks.values():
            await dock.terminate()

    def save_state(self):
        return dict()

    def restore_state(self, state):
        pass
