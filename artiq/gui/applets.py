import logging
import asyncio
import sys
import string
import shlex
import os
import subprocess
from functools import partial
from itertools import count
from types import SimpleNamespace

from PyQt6 import QtCore, QtGui, QtWidgets

from sipyco.pipe_ipc import AsyncioParentComm
from sipyco.logging_tools import LogParser
from sipyco import pyon

from artiq.gui.entries import procdesc_to_entry, EntryTreeWidget
from artiq.gui.tools import QDockWidgetCloseDetect, LayoutWidget


logger = logging.getLogger(__name__)


class EntryArea(EntryTreeWidget):
    def __init__(self):
        EntryTreeWidget.__init__(self)
        reset_all_button = QtWidgets.QPushButton("Restore defaults")
        reset_all_button.setToolTip("Reset all to default values")
        reset_all_button.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_BrowserReload))
        reset_all_button.clicked.connect(self.reset_all)
        buttons = LayoutWidget()
        buttons.layout.setColumnStretch(0, 1)
        buttons.layout.setColumnStretch(1, 0)
        buttons.layout.setColumnStretch(2, 1)
        buttons.addWidget(reset_all_button, 0, 1)
        self.setItemWidget(self.bottom_item, 1, buttons)
        self._processors = dict()

    def setattr_argument(self, key, processor, group=None, tooltip=None):
        argument = dict()
        desc = processor.describe()
        self._processors[key] = processor
        argument["desc"] = desc
        argument["group"] = group
        argument["tooltip"] = tooltip
        self.set_argument(key, argument)

    def __getattr__(self, key):
        return self.get_value(key)

    def get_value(self, key):
        entry = self._arg_to_widgets[key]["entry"]
        argument = self._arguments[key]
        processor = self._processors[key]
        return processor.process(entry.state_to_value(argument["state"]))

    def set_value(self, key, value):
        ty = self._arguments[key]["desc"]["ty"]
        if ty == "Scannable":
            desc = value.describe()
            self._arguments[key]["state"][desc["ty"]] = desc
            self._arguments[key]["state"]["selected"] = desc["ty"]
        else:
            self._arguments[key]["state"] = value
        self.update_value(key)

    def get_values(self):
        d = SimpleNamespace()
        for key in self._arguments.keys():
            setattr(d, key, self.get_value(key))
        return d

    def set_values(self, values):
        for key, value in values.items():
            self.set_value(key, value)

    def update_value(self, key):
        argument = self._arguments[key]
        self.update_argument(key, argument)

    def reset_value(self, key):
        self.reset_entry(key)

    def reset_all(self):
        for key in self._arguments.keys():
            self.reset_entry(key)


class AppletIPCServer(AsyncioParentComm):
    def __init__(self, dataset_sub, dataset_ctl, expmgr):
        AsyncioParentComm.__init__(self)
        self.dataset_sub = dataset_sub
        self.dataset_ctl = dataset_ctl
        self.expmgr = expmgr
        self.datasets = set()
        self.dataset_prefixes = []

    def write_pyon(self, obj):
        self.write(pyon.encode(obj).encode() + b"\n")

    async def read_pyon(self):
        line = await self.readline()
        return pyon.decode(line.decode())

    def _is_dataset_subscribed(self, key):
        if key in self.datasets:
            return True
        for prefix in self.dataset_prefixes:
            if key.startswith(prefix):
                return True
        return False

    def _synthesize_init(self, data):
        struct = {k: v for k, v in data.items() if self._is_dataset_subscribed(k)}
        return {"action": "init",
                "struct": struct}

    def _on_mod(self, mod):
        if mod["action"] == "init":
            if not (self.datasets or self.dataset_prefixes):
                # The dataset db connection just came online, and an applet is
                # running but did not call `subscribe` yet (e.g. because the
                # dashboard was just restarted and a previously enabled applet
                # is being re-opened). We will later synthesize an "init" `mod`
                # message once the applet actually subscribes.
                return
            mod = self._synthesize_init(mod["struct"])
        else:
            if mod["path"]:
                if not self._is_dataset_subscribed(mod["path"][0]):
                    return
            elif mod["action"] in {"setitem", "delitem"}:
                if not self._is_dataset_subscribed(mod["key"]):
                    return
        self.write_pyon({"action": "mod", "mod": mod})

    async def serve(self, embed_cb):
        self.dataset_sub.notify_cbs.append(self._on_mod)
        try:
            while True:
                obj = await self.read_pyon()
                try:
                    action = obj["action"]
                    if action == "embed":
                        size = embed_cb(obj["win_id"])
                        if size is None:
                            self.write_pyon({"action": "embed_done"})
                        else:
                            self.write_pyon({"action": "embed_done", "size_h": size.height(), "size_w": size.width()})
                    elif action == "subscribe":
                        self.datasets = obj["datasets"]
                        self.dataset_prefixes = obj["dataset_prefixes"]
                        if self.dataset_sub.model is not None:
                            mod = self._synthesize_init(
                                self.dataset_sub.model.backing_store)
                            self.write_pyon({"action": "mod", "mod": mod})
                    elif action == "set_dataset":
                        await self.dataset_ctl.set(obj["key"], obj["value"], metadata=obj["metadata"], persist=obj["persist"])
                    elif action == "update_dataset":
                        await self.dataset_ctl.update(obj["mod"])
                    elif action == "set_argument_value":
                        self.expmgr.set_argument_value(obj["expurl"], obj["key"], obj["value"])
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
            self.dataset_sub.notify_cbs.remove(self._on_mod)

    def start_server(self, embed_cb, *, loop=None):
        self.server_task = asyncio.ensure_future(
            self.serve(embed_cb), loop=loop)

    async def stop_server(self):
        if hasattr(self, "server_task"):
            self.server_task.cancel()
            await asyncio.wait([self.server_task])


class _AppletDock(QDockWidgetCloseDetect):
    def __init__(self, dataset_sub, dataset_ctl, expmgr, uid, name, spec, extra_substitutes):
        QDockWidgetCloseDetect.__init__(self, "Applet: " + name)
        self.setObjectName("applet" + str(uid))

        qfm = QtGui.QFontMetrics(self.font())
        self.setMinimumSize(20*qfm.averageCharWidth(), 5*qfm.lineSpacing())
        self.resize(40*qfm.averageCharWidth(), 10*qfm.lineSpacing())

        self.dataset_sub = dataset_sub
        self.dataset_ctl = dataset_ctl
        self.expmgr = expmgr
        self.applet_name = name
        self.spec = spec
        self.extra_substitutes = extra_substitutes

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
            self.ipc = AppletIPCServer(self.dataset_sub, self.dataset_ctl, self.expmgr)
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
            self.ipc.start_server(self.embed)
        finally:
            self.starting_stopping = False

    async def start(self):
        if self.spec["ty"] == "command":
            command_tpl = string.Template(self.spec["command"])
            python = sys.executable.replace("\\", "\\\\")
            command = command_tpl.safe_substitute(
                python=python,
                artiq_applet=python + " -m artiq.applets.",
                **self.extra_substitutes
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
        # return the size after embedding. Applet must resize to that,
        # otherwise the applet may not fit within the dock properly.
        return self.embed_widget.size()

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
    ("Progress bar", "${artiq_applet}progress_bar VALUE"),
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
            QtWidgets.QCompleter.ModelSorting.CaseSensitivelySortedModel)
        completer.setCompletionRole(QtCore.Qt.ItemDataRole.DisplayRole)
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
    def __init__(self, main_window, dataset_sub, dataset_ctl, expmgr, extra_substitutes={}, *, loop=None):
        """
        :param extra_substitutes: Map of extra ``${strings}`` to substitute in applet
            commands to their respective values.
        """
        QtWidgets.QDockWidget.__init__(self, "Applets")
        self.setObjectName("Applets")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        self.main_window = main_window
        self.dataset_sub = dataset_sub
        self.dataset_ctl = dataset_ctl
        self.expmgr = expmgr
        self.extra_substitutes = extra_substitutes
        self.applet_uids = set()

        self._loop = loop

        self.table = QtWidgets.QTreeWidget()
        self.table.setColumnCount(2)
        self.table.setHeaderLabels(["Name", "Command"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        self.table.header().setStretchLastSection(True)
        self.table.header().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)

        self.table.setDragEnabled(True)
        self.table.viewport().setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)

        self.setWidget(self.table)

        completer_delegate = _CompleterDelegate()
        self.table.setItemDelegateForColumn(1, completer_delegate)
        dataset_sub.add_setmodel_callback(completer_delegate.set_model)

        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        new_action = QtGui.QAction("New applet", self.table)
        new_action.triggered.connect(partial(self.new_with_parent, self.new))
        self.table.addAction(new_action)
        templates_menu = QtWidgets.QMenu(self.table)
        for name, template in _templates:
            spec = {"ty": "command", "command": template}
            action = QtGui.QAction(name, self.table)
            action.triggered.connect(partial(
                self.new_with_parent, self.new, spec=spec))
            templates_menu.addAction(action)
        restart_action = QtGui.QAction("New applet from template", self.table)
        restart_action.setMenu(templates_menu)
        self.table.addAction(restart_action)
        restart_action = QtGui.QAction("Restart selected applet or group", self.table)
        restart_action.setShortcut("CTRL+R")
        restart_action.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        restart_action.triggered.connect(self.restart)
        self.table.addAction(restart_action)
        delete_action = QtGui.QAction("Delete selected applet or group", self.table)
        delete_action.setShortcut("DELETE")
        delete_action.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        delete_action.triggered.connect(self.delete)
        self.table.addAction(delete_action)
        close_nondocked_action = QtGui.QAction("Close non-docked applets", self.table)
        close_nondocked_action.setShortcut("CTRL+ALT+W")
        close_nondocked_action.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        close_nondocked_action.triggered.connect(self.close_nondocked)
        self.table.addAction(close_nondocked_action)

        new_group_action = QtGui.QAction("New group", self.table)
        new_group_action.triggered.connect(partial(self.new_with_parent, self.new_group))
        self.table.addAction(new_group_action)

        self.table.itemChanged.connect(self.item_changed)

        # HACK
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
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
                    QtWidgets.QStyle.StandardPixmap.SP_FileIcon))
                item.applet_code = spec["code"]
            else:
                raise ValueError
            dock = item.applet_dock
            if dock is not None:
                dock.spec = spec
        finally:
            self.table.itemChanged.connect(self.item_changed)

    def create(self, item, name, spec):
        dock = _AppletDock(self.dataset_sub, self.dataset_ctl, self.expmgr, item.applet_uid, name, spec, self.extra_substitutes)
        self.main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)
        asyncio.ensure_future(dock.start(), loop=self._loop)
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
                if item.checkState(0) == QtCore.Qt.CheckState.Checked:
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
        asyncio.ensure_future(dock.terminate(), loop=self._loop)
        item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)

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
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
                      QtCore.Qt.ItemFlag.ItemIsUserCheckable |
                      QtCore.Qt.ItemFlag.ItemIsEditable |
                      QtCore.Qt.ItemFlag.ItemIsDragEnabled |
                      QtCore.Qt.ItemFlag.ItemNeverHasChildren |
                      QtCore.Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
        item.applet_uid = uid
        item.applet_dock = None
        item.applet_geometry = None
        item.setIcon(0, QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon))
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
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
            QtCore.Qt.ItemFlag.ItemIsEditable |
            QtCore.Qt.ItemFlag.ItemIsUserCheckable |
            QtCore.Qt.ItemFlag.ItemIsAutoTristate |
            QtCore.Qt.ItemFlag.ItemIsDragEnabled |
            QtCore.Qt.ItemFlag.ItemIsDropEnabled |
            QtCore.Qt.ItemFlag.ItemIsEnabled)
        item.setIcon(0, QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DirIcon))
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
                        asyncio.ensure_future(dock.restart(), loop=self._loop)
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
                enabled = cwi.checkState(0) == QtCore.Qt.CheckState.Checked
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
                    item.setCheckState(0, QtCore.Qt.CheckState.Checked)
            elif wis[0] == "group":
                _, name, attr, expanded, state_child = wis
                item = self.new_group(name, attr, parent=parent)
                item.setExpanded(expanded)
                self.restore_state_item(state_child, item)
            else:
                raise ValueError("Invalid item state: " + str(wis[0]))

    def restore_state(self, state):
        self.restore_state_item(state, None)

    def close_nondocked(self):
        def walk(wi):
            for i in range(wi.childCount()):
                cwi = wi.child(i)
                if cwi.ty == "applet":
                    if cwi.checkState(0) == QtCore.Qt.CheckState.Checked:
                        if cwi.applet_dock is not None:
                            if not cwi.applet_dock.isFloating():
                                continue
                        cwi.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                elif cwi.ty == "group":
                    walk(cwi)
        walk(self.table.invisibleRootItem())
