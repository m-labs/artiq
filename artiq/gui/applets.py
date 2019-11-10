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

from sipyco.pipe_ipc import AsyncioParentComm
from sipyco.logging_tools import LogParser
from sipyco import pyon

from artiq.gui.tools import QDockWidgetCloseDetect, LayoutWidget


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

    def start_server(self, embed_cb, fix_initial_size_cb):
        self.server_task = asyncio.ensure_future(
            self.serve(embed_cb, fix_initial_size_cb))

    async def stop_server(self):
        if hasattr(self, "server_task"):
            self.server_task.cancel()
            await asyncio.wait([self.server_task])


class _AppletDock(QDockWidgetCloseDetect):
    def __init__(self, datasets_sub, uid, name, spec):
        QDockWidgetCloseDetect.__init__(self, "Applet: " + name)
        self.setObjectName("applet" + str(uid))

        qfm = QtGui.QFontMetrics(self.font())
        self.setMinimumSize(20*qfm.averageCharWidth(), 5*qfm.lineSpacing())
        self.resize(40*qfm.averageCharWidth(), 10*qfm.lineSpacing())

        self.datasets_sub = datasets_sub
        self.applet_name = name
        self.spec = spec

        self.starting_stopping = False

    def rename(self, name):
        self.applet_name = name
        self.setWindowTitle("Applet: " + name)

    def _get_log_source(self):
        return "applet({})".format(self.applet_name)

    async def start_process(self, args, stdin):
        if self.starting_stopping:
            return
        self.starting_stopping = True
        try:
            self.ipc = AppletIPCServer(self.datasets_sub)
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["ARTIQ_APPLET_EMBED"] = self.ipc.get_address()
            try:
                await self.ipc.create_subprocess(
                    *args,
                    stdin=None if stdin is None else subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=env, start_new_session=True)
            except:
                logger.warning("Applet %s failed to start", self.applet_name,
                               exc_info=True)
                return
            if stdin is not None:
                self.ipc.process.stdin.write(stdin.encode())
                self.ipc.process.stdin.write_eof()
            asyncio.ensure_future(
                LogParser(self._get_log_source).stream_task(
                    self.ipc.process.stdout))
            asyncio.ensure_future(
                LogParser(self._get_log_source).stream_task(
                    self.ipc.process.stderr))
            self.ipc.start_server(self.embed, self.fix_initial_size)
        finally:
            self.starting_stopping = False

    async def start(self):
        if self.spec["ty"] == "command":
            command_tpl = string.Template(self.spec["command"])
            python = sys.executable.replace("\\", "\\\\")
            command = command_tpl.safe_substitute(
                python=python,
                artiq_applet=python + " -m artiq.applets."
            )
            logger.debug("starting command %s for %s", command, self.applet_name)
            await self.start_process(shlex.split(command), None)
        elif self.spec["ty"] == "code":
            args = [sys.executable, "-"]
            args += shlex.split(self.spec["command"])
            logger.debug("starting code applet %s", self.applet_name)
            await self.start_process(args, self.spec["code"])
        else:
            raise ValueError

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
            await self.ipc.stop_server()
            if hasattr(self.ipc, "process"):
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
    ("Big number", "${artiq_applet}big_number "
                   "NUMBER_DATASET"),
    ("Histogram", "${artiq_applet}plot_hist "
                  "COUNTS_DATASET "
                  "--x BIN_BOUNDARIES_DATASET"),
    ("XY", "${artiq_applet}plot_xy "
           "Y_DATASET --x X_DATASET "
           "--error ERROR_DATASET --fit FIT_DATASET"),
    ("XY + Histogram", "${artiq_applet}plot_xy_hist "
                       "X_DATASET "
                       "HIST_BIN_BOUNDARIES_DATASET "
                       "HISTS_COUNTS_DATASET"),
    ("Image", "${artiq_applet}image IMG_DATASET"),
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
            # "TODO: Optimize updates in the source model"
            #    - Qt (qcompleter.cpp), never ceasing to disappoint.
            # HACK:
            # In the meantime, block dataChanged signals from the model.
            # dataChanged never changes the content of the QCompleter in our
            # case, but causes unnecessary flickering and trashing of the user
            # selection when datasets are modified due to Qt's naive handler.
            # Doing this is of course convoluted due to Qt's arrogance
            # about private fields and not letting users knows what
            # slots are connected to signals, but thanks to the complicated
            # model system there is a short dirty hack in this particular case.
            nodatachanged_model = QtCore.QIdentityProxyModel()
            nodatachanged_model.setSourceModel(self.model)
            completer.setModel(nodatachanged_model)
            nodatachanged_model.dataChanged.disconnect()
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
        self.applet_uids = set()

        self.table = QtWidgets.QTreeWidget()
        self.table.setColumnCount(2)
        self.table.setHeaderLabels(["Name", "Command"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self.table.header().setStretchLastSection(True)
        self.table.header().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents)
        self.table.setTextElideMode(QtCore.Qt.ElideNone)

        self.table.setDragEnabled(True)
        self.table.viewport().setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)

        self.setWidget(self.table)

        completer_delegate = _CompleterDelegate()
        self.table.setItemDelegateForColumn(1, completer_delegate)
        datasets_sub.add_setmodel_callback(completer_delegate.set_model)

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        new_action = QtWidgets.QAction("New applet", self.table)
        new_action.triggered.connect(partial(self.new_with_parent, self.new))
        self.table.addAction(new_action)
        templates_menu = QtWidgets.QMenu()
        for name, template in _templates:
            spec = {"ty": "command", "command": template}
            action = QtWidgets.QAction(name, self.table)
            action.triggered.connect(partial(
                self.new_with_parent, self.new, spec=spec))
            templates_menu.addAction(action)
        restart_action = QtWidgets.QAction("New applet from template", self.table)
        restart_action.setMenu(templates_menu)
        self.table.addAction(restart_action)
        restart_action = QtWidgets.QAction("Restart selected applet or group", self.table)
        restart_action.setShortcut("CTRL+R")
        restart_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        restart_action.triggered.connect(self.restart)
        self.table.addAction(restart_action)
        delete_action = QtWidgets.QAction("Delete selected applet or group", self.table)
        delete_action.setShortcut("DELETE")
        delete_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        delete_action.triggered.connect(self.delete)
        self.table.addAction(delete_action)
        new_group_action = QtWidgets.QAction("New group", self.table)
        new_group_action.triggered.connect(partial(self.new_with_parent, self.new_group))
        self.table.addAction(new_group_action)

        self.table.itemChanged.connect(self.item_changed)

        # HACK
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.open_editor)

    def open_editor(self, item, column):
        if column != 1 or item.ty != "group":
            self.table.editItem(item, column)

    def get_spec(self, item):
        if item.applet_spec_ty == "command":
            return {"ty": "command", "command": item.text(1)}
        elif item.applet_spec_ty == "code":
            return {"ty": "code", "code": item.applet_code,
                    "command": item.text(1)}
        else:
            raise ValueError

    def set_spec(self, item, spec):
        self.table.itemChanged.disconnect()
        try:
            item.applet_spec_ty = spec["ty"]
            item.setText(1, spec["command"])
            if spec["ty"] == "command":
                item.setIcon(1, QtGui.QIcon())
                if hasattr(item, "applet_code"):
                    del item.applet_code
            elif spec["ty"] == "code":
                item.setIcon(1, QtWidgets.QApplication.style().standardIcon(
                    QtWidgets.QStyle.SP_FileIcon))
                item.applet_code = spec["code"]
            else:
                raise ValueError
            dock = item.applet_dock
            if dock is not None:
                dock.spec = spec
        finally:
            self.table.itemChanged.connect(self.item_changed)

    def create(self, item, name, spec):
        dock = _AppletDock(self.datasets_sub, item.applet_uid, name, spec)
        self.main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        dock.setFloating(True)
        asyncio.ensure_future(dock.start())
        dock.sigClosed.connect(partial(self.on_dock_closed, item, dock))
        return dock

    def item_changed(self, item, column):
        if item.ty == "applet":
            new_value = item.text(column)
            dock = item.applet_dock
            if dock is not None:
                if column == 0:
                    dock.rename(new_value)
                else:
                    dock.spec = self.get_spec(item)

            if column == 0:
                if item.checkState(0) == QtCore.Qt.Checked:
                    if item.applet_dock is None:
                        name = item.text(0)
                        spec = self.get_spec(item)
                        dock = self.create(item, name, spec)
                        item.applet_dock = dock
                        if item.applet_geometry is not None:
                            dock.restoreGeometry(item.applet_geometry)
                            # geometry is now handled by main window state
                            item.applet_geometry = None
                else:
                    dock = item.applet_dock
                    item.applet_dock = None
                    if dock is not None:
                        # This calls self.on_dock_closed
                        dock.close()
        elif item.ty == "group":
            # To Qt's credit, it already does everything for us here.
            pass
        else:
            raise ValueError

    def on_dock_closed(self, item, dock):
        item.applet_geometry = dock.saveGeometry()
        asyncio.ensure_future(dock.terminate())
        item.setCheckState(0, QtCore.Qt.Unchecked)

    def get_untitled(self):
        existing_names = set()
        def walk(wi):
            for i in range(wi.childCount()):
                cwi = wi.child(i)
                existing_names.add(cwi.text(0))
                walk(cwi)
        walk(self.table.invisibleRootItem())

        i = 1
        name = "untitled"
        while name in existing_names:
            i += 1
            name = "untitled " + str(i)
        return name

    def new(self, uid=None, name=None, spec=None, parent=None):
        if uid is None:
            uid = next(i for i in count() if i not in self.applet_uids)
        if spec is None:
            spec = {"ty": "command", "command": ""}
        assert uid not in self.applet_uids, uid
        self.applet_uids.add(uid)

        if name is None:
            name = self.get_untitled()
        item = QtWidgets.QTreeWidgetItem([name, ""])
        item.ty = "applet"
        item.setFlags(QtCore.Qt.ItemIsSelectable |
                      QtCore.Qt.ItemIsUserCheckable |
                      QtCore.Qt.ItemIsEditable |
                      QtCore.Qt.ItemIsDragEnabled |
                      QtCore.Qt.ItemNeverHasChildren |
                      QtCore.Qt.ItemIsEnabled)
        item.setCheckState(0, QtCore.Qt.Unchecked)
        item.applet_uid = uid
        item.applet_dock = None
        item.applet_geometry = None
        item.setIcon(0, QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_ComputerIcon))
        self.set_spec(item, spec)
        if parent is None:
            self.table.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def new_group(self, name=None, attr="", parent=None):
        if name is None:
            name = self.get_untitled()
        item = QtWidgets.QTreeWidgetItem([name, attr])
        item.ty = "group"
        item.setFlags(QtCore.Qt.ItemIsSelectable |
            QtCore.Qt.ItemIsEditable |
            QtCore.Qt.ItemIsUserCheckable |
            QtCore.Qt.ItemIsTristate |
            QtCore.Qt.ItemIsDragEnabled |
            QtCore.Qt.ItemIsDropEnabled |
            QtCore.Qt.ItemIsEnabled)
        item.setIcon(0, QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DirIcon))
        if parent is None:
            self.table.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def new_with_parent(self, cb, **kwargs):
        parent = None
        selection = self.table.selectedItems()
        if selection:
            parent = selection[0]
            if parent.ty == "applet":
                parent = parent.parent()
        if parent is not None:
            parent.setExpanded(True)
        cb(parent=parent, **kwargs)

    def restart(self):
        selection = self.table.selectedItems()
        if selection:
            item = selection[0]
            def walk(wi):
                if wi.ty == "applet":
                    dock = wi.applet_dock
                    if dock is not None:
                        asyncio.ensure_future(dock.restart())
                elif wi.ty == "group":
                    for i in range(wi.childCount()):
                        walk(wi.child(i))
                else:
                    raise ValueError
            walk(item)

    def delete(self):
        selection = self.table.selectedItems()
        if selection:
            item = selection[0]

            def recursive_delete(wi):
                if wi.ty == "applet":
                    dock = wi.applet_dock
                    if dock is not None:
                        # This calls self.on_dock_closed
                        dock.close()
                    self.applet_uids.remove(wi.applet_uid)
                elif wi.ty == "group":
                    for i in range(wi.childCount()):
                        recursive_delete(wi.child(i))
                else:
                    raise ValueError
            recursive_delete(item)

            parent = item.parent()
            if parent is None:
                parent = self.table.invisibleRootItem()
            parent.removeChild(item)

    async def stop(self):
        async def walk(wi):
            for row in range(wi.childCount()):
                cwi = wi.child(row)
                if cwi.ty == "applet":
                    dock = cwi.applet_dock
                    if dock is not None:
                        await dock.terminate()
                elif cwi.ty == "group":
                    await walk(cwi)
                else:
                    raise ValueError
        await walk(self.table.invisibleRootItem())

    def save_state_item(self, wi):
        state = []
        for row in range(wi.childCount()):
            cwi = wi.child(row)
            if cwi.ty == "applet":
                uid = cwi.applet_uid
                enabled = cwi.checkState(0) == QtCore.Qt.Checked
                name = cwi.text(0)
                spec = self.get_spec(cwi)
                geometry = cwi.applet_geometry
                if geometry is not None:
                    geometry = bytes(geometry)
                state.append(("applet", uid, enabled, name, spec, geometry))
            elif cwi.ty == "group":
                name = cwi.text(0)
                attr = cwi.text(1)
                expanded = cwi.isExpanded()
                state_child = self.save_state_item(cwi)
                state.append(("group", name, attr, expanded, state_child))
            else:
                raise ValueError
        return state

    def save_state(self):
        return self.save_state_item(self.table.invisibleRootItem())

    def restore_state_item(self, state, parent):
        for wis in state:
            if wis[0] == "applet":
                _, uid, enabled, name, spec, geometry = wis
                if spec["ty"] not in {"command", "code"}:
                    raise ValueError("Invalid applet spec type: "
                                     + str(spec["ty"]))
                item = self.new(uid, name, spec, parent=parent)
                if geometry is not None:
                    geometry = QtCore.QByteArray(geometry)
                    item.applet_geometry = geometry
                if enabled:
                    item.setCheckState(0, QtCore.Qt.Checked)
            elif wis[0] == "group":
                _, name, attr, expanded, state_child = wis
                item = self.new_group(name, attr, parent=parent)
                item.setExpanded(expanded)
                self.restore_state_item(state_child, item)
            else:
                raise ValueError("Invalid item state: " + str(wis[0]))

    def restore_state(self, state):
        self.restore_state_item(state, None)
