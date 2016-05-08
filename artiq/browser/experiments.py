import asyncio
import logging
import os
from functools import partial
from collections import OrderedDict

from PyQt5 import QtCore, QtGui, QtWidgets
import h5py

from artiq import __artiq_dir__ as artiq_dir
from artiq.gui.tools import LayoutWidget, log_level_to_name, getOpenFileName
from artiq.gui.entries import argty_to_entry
from artiq.protocols import pyon
from artiq.master.worker import Worker

logger = logging.getLogger(__name__)


class _WheelFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if (event.type() == QtCore.QEvent.Wheel and
                event.modifiers() != QtCore.Qt.NoModifier):
            event.ignore()
            return True
        return False


class _ArgumentEditor(QtWidgets.QTreeWidget):
    def __init__(self, dock):
        QtWidgets.QTreeWidget.__init__(self)
        self.setColumnCount(3)
        self.header().setStretchLastSection(False)
        try:
            set_resize_mode = self.header().setSectionResizeMode
        except AttributeError:
            set_resize_mode = self.header().setResizeMode
        set_resize_mode(0, QtWidgets.QHeaderView.ResizeToContents)
        set_resize_mode(1, QtWidgets.QHeaderView.Stretch)
        set_resize_mode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.header().setVisible(False)
        self.setSelectionMode(self.NoSelection)
        self.setHorizontalScrollMode(self.ScrollPerPixel)
        self.setVerticalScrollMode(self.ScrollPerPixel)

        self.viewport().installEventFilter(_WheelFilter(self.viewport()))

        self._groups = dict()
        self._arg_to_entry_widgetitem = dict()
        self._dock = dock

        if not self._dock.arguments:
            self.addTopLevelItem(QtWidgets.QTreeWidgetItem(["No arguments"]))

        for name, argument in self._dock.arguments.items():
            try:
                entry = argty_to_entry[argument["desc"]["ty"]](argument)
            except:
                print(name, argument)
            widget_item = QtWidgets.QTreeWidgetItem([name])
            self._arg_to_entry_widgetitem[name] = entry, widget_item

            if argument["group"] is None:
                self.addTopLevelItem(widget_item)
            else:
                self._get_group(argument["group"]).addChild(widget_item)
            self.setItemWidget(widget_item, 1, entry)
            recompute_argument = QtWidgets.QToolButton()
            recompute_argument.setToolTip("Re-run the experiment's build "
                                          "method and take the default value")
            recompute_argument.setIcon(
                QtWidgets.QApplication.style().standardIcon(
                    QtWidgets.QStyle.SP_BrowserReload))
            recompute_argument.clicked.connect(
                partial(self._recompute_argument_clicked, name))
            fix_layout = LayoutWidget()
            fix_layout.addWidget(recompute_argument)
            self.setItemWidget(widget_item, 2, fix_layout)

        widget_item = QtWidgets.QTreeWidgetItem()
        self.addTopLevelItem(widget_item)
        recompute_arguments = QtWidgets.QPushButton("Recompute all arguments")
        recompute_arguments.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_BrowserReload))
        recompute_arguments.clicked.connect(self._recompute_arguments_clicked)

        buttons = LayoutWidget()
        buttons.addWidget(recompute_arguments, 1, 1)
        for i, s in enumerate((1, 0, 0, 1)):
            buttons.layout.setColumnStretch(i, s)
        self.setItemWidget(widget_item, 1, buttons)

    def _get_group(self, name):
        if name in self._groups:
            return self._groups[name]
        group = QtWidgets.QTreeWidgetItem([name])
        for c in 0, 1:
            group.setBackground(c, QtGui.QBrush(QtGui.QColor(100, 100, 100)))
            group.setForeground(c, QtGui.QBrush(QtGui.QColor(220, 220, 255)))
            font = group.font(c)
            font.setBold(True)
            group.setFont(c, font)
        self.addTopLevelItem(group)
        self._groups[name] = group
        return group

    def _recompute_arguments_clicked(self):
        asyncio.ensure_future(self._dock.recompute_arguments())

    def _recompute_argument_clicked(self, name):
        asyncio.ensure_future(self._recompute_argument(name))

    async def _recompute_argument(self, name):
        try:
            arginfo = await self._dock.compute_arginfo()
        except:
            logger.error("Could not recompute argument '%s' of '%s'",
                         name, self._dock.expurl, exc_info=True)
            return
        argument = self._dock.arguments[name]

        procdesc = arginfo[name][0]
        state = argty_to_entry[procdesc["ty"]].default_state(procdesc)
        argument["desc"] = procdesc
        argument["state"] = state

        old_entry, widget_item = self._arg_to_entry_widgetitem[name]
        old_entry.deleteLater()

        entry = argty_to_entry[procdesc["ty"]](argument)
        self._arg_to_entry_widgetitem[name] = entry, widget_item
        self.setItemWidget(widget_item, 1, entry)

    def save_state(self):
        expanded = []
        for k, v in self._groups.items():
            if v.isExpanded():
                expanded.append(k)
        return {"expanded": expanded}

    def restore_state(self, state):
        for e in state["expanded"]:
            try:
                self._groups[e].setExpanded(True)
            except KeyError:
                pass


log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class _ExperimentDock(QtWidgets.QMdiSubWindow):
    sigClosed = QtCore.pyqtSignal()

    def __init__(self, area, expurl, arguments, worker_handlers):
        QtWidgets.QMdiSubWindow.__init__(self)
        self.setWindowTitle(expurl)
        self.setWindowIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_FileDialogContentsView))
        self.setAcceptDrops(True)

        self.layout = QtWidgets.QGridLayout()
        top_widget = QtWidgets.QWidget()
        top_widget.setLayout(self.layout)
        self.setWidget(top_widget)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self._area = area
        self.expurl = expurl
        self.worker_handlers = worker_handlers
        self.arguments = arguments

        self.argeditor = _ArgumentEditor(self)
        self.layout.addWidget(self.argeditor, 0, 0, 1, 5)
        self.layout.setRowStretch(0, 1)

        self.options = {"log_level": logging.WARNING}

        log_level = QtWidgets.QComboBox()
        log_level.addItems(log_levels)
        log_level.setCurrentIndex(1)
        log_level.setToolTip("Minimum level for log entry production")
        log_level_label = QtWidgets.QLabel("Logging level:")
        log_level_label.setToolTip("Minimum level for log message production")
        self.layout.addWidget(log_level_label, 3, 0)
        self.layout.addWidget(log_level, 3, 1)

        log_level.setCurrentIndex(log_levels.index(
            log_level_to_name(self.options["log_level"])))

        def update_log_level(index):
            self.options["log_level"] = getattr(logging,
                                                log_level.currentText())
        log_level.currentIndexChanged.connect(update_log_level)
        self.log_level = log_level

        submit = QtWidgets.QPushButton("Submit")
        submit.setIcon(QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DialogOkButton))
        submit.setToolTip("Schedule the experiment (Ctrl+Return)")
        submit.setShortcut("CTRL+RETURN")
        submit.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                             QtWidgets.QSizePolicy.Expanding)
        self.layout.addWidget(submit, 1, 4, 2, 1)
        submit.clicked.connect(self.submit_clicked)

        reqterm = QtWidgets.QPushButton("Terminate instances")
        reqterm.setIcon(QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DialogCancelButton))
        reqterm.setToolTip("Request termination of instances (Ctrl+Backspace)")
        reqterm.setShortcut("CTRL+BACKSPACE")
        reqterm.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                              QtWidgets.QSizePolicy.Expanding)
        self.layout.addWidget(reqterm, 3, 4)
        reqterm.clicked.connect(self.reqterm_clicked)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat("text/uri-list"):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for uri in ev.mimeData().urls():
            if uri.scheme() == "file":
                logger.info("loading HDF5 arguments from %s", uri.path())
                asyncio.ensure_future(self._load_hdf5_task(uri.path()))
        ev.acceptProposedAction()

    async def _recompute_arguments(self, overrides={}):
        try:
            arginfo = await self._area.compute_arginfo(self.expurl)
        except:
            logger.error("Could not recompute arguments of '%s'",
                         self.expurl, exc_info=True)
            return
        for k, v in overrides.items():
            arginfo[k][0]["default"] = v
        self.arguments = self._area.initialize_submission_arguments(arginfo)

        self.argeditor.deleteLater()
        self.argeditor = _ArgumentEditor(self)
        self.layout.addWidget(self.argeditor, 0, 0, 1, 5)

    async def _load_hdf5_task(self, filename):
        try:
            with h5py.File(filename, "r") as f:
                expid = f["expid"][()]
            expid = pyon.decode(expid)
            arguments = expid["arguments"]
        except:
            logger.error("Could not retrieve expid from HDF5 file",
                         exc_info=True)
            return

        try:
            self.log_level.setCurrentIndex(log_levels.index(
                log_level_to_name(expid["log_level"])))
        except:
            logger.error("Could not set submission options from HDF5 expid",
                         exc_info=True)
            return

        await self._recompute_arguments(arguments)

    def submit_clicked(self):
        try:
            pass  # TODO
        except:
            # May happen when experiment has been removed
            # from repository/explist
            logger.error("Failed to submit '%s'",
                         self.expurl, exc_info=True)

    def reqterm_clicked(self):
        try:
            pass  # TODO
        except:
            # May happen when experiment has been removed
            # from repository/explist
            logger.error("Failed to request termination of instances of '%s'",
                         self.expurl, exc_info=True)

    def closeEvent(self, event):
        self.sigClosed.emit()
        QtWidgets.QMdiSubWindow.closeEvent(self, event)

    def save_state(self):
        return {
            "argeditor": self.argeditor.save_state(),
            "geometry": bytes(self.saveGeometry()),
            "options": self.options,
        }

    def restore_state(self, state):
        self.argeditor.restore_state(state["argeditor"])
        self.restoreGeometry(QtCore.QByteArray(state["geometry"]))
        self.options = state["options"]


class ExperimentsArea(QtWidgets.QMdiArea):
    def __init__(self, root, datasets_sub):
        QtWidgets.QMdiArea.__init__(self)
        self.pixmap = QtGui.QPixmap(os.path.join(
            artiq_dir, "gui", "logo20.svg"))
        self.current_dir = root
        self.setToolTip("Click to open experiment")

        self.open_experiments = []

        self.worker_handlers = {
            "get_device_db": lambda: None,
            "get_device": lambda k: None,
            "get_dataset": lambda k: 0,  # TODO
            "update_dataset": lambda k, v: None,
        }

    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            asyncio.ensure_future(self._select_experiment_task())

    def paintEvent(self, event):
        QtWidgets.QMdiArea.paintEvent(self, event)
        painter = QtGui.QPainter(self.viewport())
        x = (self.width() - self.pixmap.width())//2
        y = (self.height() - self.pixmap.height())//2
        painter.setOpacity(0.5)
        painter.drawPixmap(x, y, self.pixmap)

    def save_state(self):
        return {"experiments": [{
            "expurl": dock.expurl,
            "arguments": dock.arguments,
            "dock": dock.save_state(),
        } for dock in self.open_experiments]}

    def restore_state(self, state):
        if self.open_experiments:
            raise NotImplementedError
        for ex_state in state["experiments"]:
            dock = self.open_experiment(ex_state["expurl"],
                                        ex_state["arguments"])
            dock.restore_state(ex_state["dock"])

    def _select_experiment(self):
        asyncio.ensure_future(self._select_experiment_task())

    async def _select_experiment_task(self):
        try:
            file = await getOpenFileName(
                self, "Open experiment", self.current_dir,
                "Experiments (*.py);;All files (*.*)")
        except asyncio.CancelledError:
            return
        self.current_dir = os.path.dirname(file)
        logger.info("opening experiment %s", file)
        description = await self.examine(file)
        for class_name, class_desc in description.items():
            expurl = "{}@{}".format(class_name, file)
            arguments = self.initialize_submission_arguments(
                class_desc["arginfo"])
            self.open_experiment(expurl, arguments)

    def initialize_submission_arguments(self, arginfo):
        arguments = OrderedDict()
        for name, (procdesc, group) in arginfo.items():
            state = argty_to_entry[procdesc["ty"]].default_state(procdesc)
            arguments[name] = {
                "desc": procdesc,
                "group": group,
                "state": state  # mutated by entries
            }
        return arguments

    async def examine(self, file):
        worker = Worker(self.worker_handlers)
        try:
            return await worker.examine("examine", file)
        finally:
            await worker.close()

    async def compute_arginfo(self, expurl):
        class_name, file = expurl.split("@", maxsplit=1)
        desc = await self.examine(file)
        return desc[class_name]["arginfo"]

    def open_experiment(self, expurl, arguments):
        try:
            dock = _ExperimentDock(self, expurl, arguments,
                                   self.worker_handlers)
        except:
            logger.warning("Failed to create experiment dock for %s, "
                           "retrying with arguments reset", expurl,
                           exc_info=True)
            dock = _ExperimentDock(self, expurl, {}, self.worker_handlers)
            asyncio.ensure_future(dock._recompute_arguments())
        self.addSubWindow(dock)
        dock.show()
        dock.sigClosed.connect(partial(self.on_dock_closed, dock))
        self.open_experiments.append(dock)
        return dock

    def on_dock_closed(self, dock):
        self.open_experiments.remove(dock)
