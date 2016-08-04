import logging
import asyncio
import sys
import string
import shlex
import os
import subprocess
from functools import partial
from itertools import count

from PyQt5 import QtCore, QtGui, QtWidgets

from artiq.protocols.pipe_ipc import AsyncioParentComm
from artiq.protocols.logging import LogParser
from artiq.protocols import pyon
from artiq.gui.tools import QDockWidgetCloseDetect


logger = logging.getLogger(__name__)


class AppletIPCServer(AsyncioParentComm):
    def __init__(self, datasets_sub):
        AsyncioParentComm.__init__(self)
        self.datasets_sub = datasets_sub
        self.datasets = set()

    def write_pyon(self, obj):
        self.write(pyon.encode(obj).encode() + b"\n")

    async def read_pyon(self):
        line = await self.readline()
        return pyon.decode(line.decode())

    def _synthesize_init(self, data):
        struct = {k: v for k, v in data.items() if k in self.datasets}
        return {"action": "init",
                "struct": struct}

    def _on_mod(self, mod):
        if mod["action"] == "init":
            mod = self._synthesize_init(mod["struct"])
        else:
            if mod["path"]:
                if mod["path"][0] not in self.datasets:
                    return
            elif mod["action"] in {"setitem", "delitem"}:
                if mod["key"] not in self.datasets:
                    return
        self.write_pyon({"action": "mod", "mod": mod})

    async def serve(self, embed_cb, fix_initial_size_cb):
        self.datasets_sub.notify_cbs.append(self._on_mod)
        try:
            while True:
                obj = await self.read_pyon()
                try:
                    action = obj["action"]
                    if action == "embed":
                        embed_cb(obj["win_id"])
                        self.write_pyon({"action": "embed_done"})
                    elif action == "fix_initial_size":
                        fix_initial_size_cb()
                    elif action == "subscribe":
                        self.datasets = obj["datasets"]
                        if self.datasets_sub.model is not None:
                            mod = self._synthesize_init(
                                self.datasets_sub.model.backing_store)
                            self.write_pyon({"action": "mod", "mod": mod})
                    else:
                        raise ValueError("unknown action in applet message")
                except:
                    logger.warning("error processing applet message",
                                   exc_info=True)
                    self.write_pyon({"action": "error"})
        except asyncio.CancelledError:
            pass
        except:
            logger.error("error processing data from applet, "
                         "server stopped", exc_info=True)
        finally:
            self.datasets_sub.notify_cbs.remove(self._on_mod)

    def start(self, embed_cb, fix_initial_size_cb):
        self.server_task = asyncio.ensure_future(
            self.serve(embed_cb, fix_initial_size_cb))

    async def stop(self):
        self.server_task.cancel()
        await asyncio.wait([self.server_task])


class _AppletDock(QDockWidgetCloseDetect):
    def __init__(self, datasets_sub, uid, name, command):
        QDockWidgetCloseDetect.__init__(self, "Applet: " + name)
        self.setObjectName("applet" + str(uid))

        qfm = QtGui.QFontMetrics(self.font())
        self.setMinimumSize(20*qfm.averageCharWidth(), 5*qfm.lineSpacing())
        self.resize(40*qfm.averageCharWidth(), 10*qfm.lineSpacing())

        self.datasets_sub = datasets_sub
        self.applet_name = name
        self.command = command

        self.starting_stopping = False

    def rename(self, name):
        self.applet_name = name
        self.setWindowTitle("Applet: " + name)

    def _get_log_source(self):
        return "applet({})".format(self.applet_name)

    async def start(self):
        if self.starting_stopping:
            return
        self.starting_stopping = True
        try:
            self.ipc = AppletIPCServer(self.datasets_sub)
            if "$ipc_address" not in self.command:
                logger.warning("IPC address missing from command for %s",
                               self.applet_name)
            command_tpl = string.Template(self.command)
            command = command_tpl.safe_substitute(
                python=sys.executable.replace("\\", "\\\\"),
                ipc_address=self.ipc.get_address().replace("\\", "\\\\")
            )
            logger.debug("starting command %s for %s", command, self.applet_name)
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            try:
                await self.ipc.create_subprocess(
                    *shlex.split(command),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=env, start_new_session=True)
            except:
                logger.warning("Applet %s failed to start", self.applet_name,
                               exc_info=True)
            asyncio.ensure_future(
                LogParser(self._get_log_source).stream_task(
                    self.ipc.process.stdout))
            asyncio.ensure_future(
                LogParser(self._get_log_source).stream_task(
                    self.ipc.process.stderr))
            self.ipc.start(self.embed, self.fix_initial_size)
        finally:
            self.starting_stopping = False

    def embed(self, win_id):
        logger.debug("capturing window 0x%x for %s", win_id, self.applet_name)
        self.embed_window = QtGui.QWindow.fromWinId(win_id)
        self.embed_widget = QtWidgets.QWidget.createWindowContainer(
            self.embed_window)
        self.setWidget(self.embed_widget)

    # HACK: This function would not be needed if Qt window embedding
    # worked correctly.
    def fix_initial_size(self):
        self.embed_window.resize(self.embed_widget.size())

    async def terminate(self, delete_self=True):
        if self.starting_stopping:
            return
        self.starting_stopping = True

        if hasattr(self, "ipc"):
            await self.ipc.stop()
            self.ipc.write_pyon({"action": "terminate"})
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

        if hasattr(self, "embed_widget"):
            self.embed_widget.deleteLater()
            del self.embed_widget

        self.starting_stopping = False

        if delete_self:
            self.deleteLater()

    async def restart(self):
        await self.terminate(False)
        await self.start()


_templates = [
    ("Big number", "$python -m artiq.applets.big_number "
                   "--embed $ipc_address NUMBER_DATASET"),
    ("Histogram", "$python -m artiq.applets.plot_hist "
                  "--embed $ipc_address COUNTS_DATASET "
                  "--x BIN_BOUNDARIES_DATASET"),
    ("XY", "$python -m artiq.applets.plot_xy "
           "--embed $ipc_address Y_DATASET --x X_DATASET "
           "--error ERROR_DATASET --fit FIT_DATASET"),
    ("XY + Histogram", "$python -m artiq.applets.plot_xy_hist "
                       "--embed $ipc_address X_DATASET "
                       "HIST_BIN_BOUNDARIES_DATASET "
                       "HISTS_COUNTS_DATASET"),
    ("Image", "$python -m artiq.applets.image "
                  "--embed $ipc_address IMG_DATASET"),
]


# Based on:
# http://blog.elentok.com/2011/08/autocomplete-textbox-for-multiple.html

class _AutoCompleteEdit(QtWidgets.QLineEdit):
    def __init__(self, parent, completer):
        QtWidgets.QLineEdit.__init__(self, parent)
        self._completer = completer
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert_completion)

    def _insert_completion(self, completion):
        parents = self._completer.completionPrefix()
        idx = max(parents.rfind("."), parents.rfind("/"))
        if idx >= 0:
            parents = parents[:idx+1]
            completion = parents + completion

        text = self.text()
        cursor = self.cursorPosition()

        word_start = cursor - 1
        while word_start >= 0 and text[word_start] != " ":
            word_start -= 1
        word_start += 1
        word_end = cursor
        while word_end < len(text) and text[word_end] != " ":
            word_end += 1

        self.setText(text[:word_start] + completion + text[word_end:])
        self.setCursorPosition(word_start + len(completion))

    def _update_completer_popup_items(self, completion_prefix):
        self._completer.setCompletionPrefix(completion_prefix)
        self._completer.popup().setCurrentIndex(
            self._completer.completionModel().index(0, 0))

    def _text_before_cursor(self):
        text = self.text()
        text_before_cursor = ""
        i = self.cursorPosition() - 1
        while i >= 0 and text[i] != " ":
            text_before_cursor = text[i] + text_before_cursor
            i -= 1
        return text_before_cursor

    def keyPressEvent(self, event):
        QtWidgets.QLineEdit.keyPressEvent(self, event)
        completion_prefix = self._text_before_cursor()
        if completion_prefix != self._completer.completionPrefix():
            self._update_completer_popup_items(completion_prefix)
        if completion_prefix:
            self._completer.complete()
        else:
            self._completer.popup().hide()


class _CompleterDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        completer = QtWidgets.QCompleter()
        completer.splitPath = lambda path: path.replace("/", ".").split(".")
        completer.setModelSorting(
            QtWidgets.QCompleter.CaseSensitivelySortedModel)
        completer.setCompletionRole(QtCore.Qt.DisplayRole)
        if hasattr(self, "model"):
            completer.setModel(self.model)
        return _AutoCompleteEdit(parent, completer)

    def set_model(self, model):
        self.model = model


class AppletsDock(QtWidgets.QDockWidget):
    def __init__(self, main_window, datasets_sub):
        QtWidgets.QDockWidget.__init__(self, "Applets")
        self.setObjectName("Applets")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        self.main_window = main_window
        self.datasets_sub = datasets_sub
        self.dock_to_checkbox = dict()
        self.applet_uids = set()

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Enable", "Name", "Command"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setTextElideMode(QtCore.Qt.ElideNone)
        self.setWidget(self.table)

        completer_delegate = _CompleterDelegate()
        self.table.setItemDelegateForColumn(2, completer_delegate)
        datasets_sub.add_setmodel_callback(completer_delegate.set_model)

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        new_action = QtWidgets.QAction("New applet", self.table)
        new_action.triggered.connect(lambda: self.new())
        self.table.addAction(new_action)
        templates_menu = QtWidgets.QMenu()
        for name, template in _templates:
            action = QtWidgets.QAction(name, self.table)
            action.triggered.connect(partial(self.new_template, template))
            templates_menu.addAction(action)
        restart_action = QtWidgets.QAction("New applet from template", self.table)
        restart_action.setMenu(templates_menu)
        self.table.addAction(restart_action)
        restart_action = QtWidgets.QAction("Restart selected applet", self.table)
        restart_action.setShortcut("CTRL+R")
        restart_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        restart_action.triggered.connect(self.restart)
        self.table.addAction(restart_action)
        delete_action = QtWidgets.QAction("Delete selected applet", self.table)
        delete_action.setShortcut("DELETE")
        delete_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        delete_action.triggered.connect(self.delete)
        self.table.addAction(delete_action)

        self.table.cellChanged.connect(self.cell_changed)

    def create(self, uid, name, command):
        dock = _AppletDock(self.datasets_sub, uid, name, command)
        self.main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        dock.setFloating(True)
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
                    dock = self.create(item.applet_uid, name, command)
                    item.applet_dock = dock
                    if item.applet_geometry is not None:
                        dock.restoreGeometry(item.applet_geometry)
                        # geometry is now handled by main window state
                        item.applet_geometry = None
                    self.dock_to_checkbox[dock] = item
            else:
                dock = item.applet_dock
                if dock is not None:
                    # This calls self.on_dock_closed
                    dock.close()
        elif column == 1 or column == 2:
            new_value = self.table.item(row, column).text()
            dock = self.table.item(row, 0).applet_dock
            if dock is not None:
                if column == 1:
                    dock.rename(new_value)
                else:
                    dock.command = new_value

    def on_dock_closed(self, dock):
        checkbox_item = self.dock_to_checkbox[dock]
        checkbox_item.applet_dock = None
        checkbox_item.applet_geometry = dock.saveGeometry()
        asyncio.ensure_future(dock.terminate())
        del self.dock_to_checkbox[dock]
        checkbox_item.setCheckState(QtCore.Qt.Unchecked)

    def new(self, uid=None):
        if uid is None:
            uid = next(i for i in count() if i not in self.applet_uids)
        assert uid not in self.applet_uids, uid
        self.applet_uids.add(uid)

        row = self.table.rowCount()
        self.table.insertRow(row)
        checkbox = QtWidgets.QTableWidgetItem()
        checkbox.setFlags(QtCore.Qt.ItemIsSelectable |
                          QtCore.Qt.ItemIsUserCheckable |
                          QtCore.Qt.ItemIsEnabled)
        checkbox.setCheckState(QtCore.Qt.Unchecked)
        checkbox.applet_uid = uid
        checkbox.applet_dock = None
        checkbox.applet_geometry = None
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
            dock = self.table.item(row, 0).applet_dock
            if dock is not None:
                asyncio.ensure_future(dock.restart())

    def delete(self):
        selection = self.table.selectedRanges()
        if selection:
            row = selection[0].topRow()
            item = self.table.item(row, 0)
            dock = item.applet_dock
            if dock is not None:
                # This calls self.on_dock_closed
                dock.close()
            self.applet_uids.remove(item.applet_uid)
            self.table.removeRow(row)

    async def stop(self):
        for row in range(self.table.rowCount()):
            dock = self.table.item(row, 0).applet_dock
            if dock is not None:
                await dock.terminate()

    def save_state(self):
        state = []
        for row in range(self.table.rowCount()):
            uid = self.table.item(row, 0).applet_uid
            enabled = self.table.item(row, 0).checkState() == QtCore.Qt.Checked
            name = self.table.item(row, 1).text()
            command = self.table.item(row, 2).text()
            geometry = self.table.item(row, 0).applet_geometry
            if geometry is not None:
                geometry = bytes(geometry)
            state.append((uid, enabled, name, command, geometry))
        return state

    def restore_state(self, state):
        for uid, enabled, name, command, geometry in state:
            row = self.new(uid)
            item = QtWidgets.QTableWidgetItem()
            item.setText(name)
            self.table.setItem(row, 1, item)
            item = QtWidgets.QTableWidgetItem()
            item.setText(command)
            self.table.setItem(row, 2, item)
            if geometry is not None:
                geometry = QtCore.QByteArray(geometry)
                self.table.item(row, 0).applet_geometry = geometry
            if enabled:
                self.table.item(row, 0).setCheckState(QtCore.Qt.Checked)
