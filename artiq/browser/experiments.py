import asyncio
import logging
import os
from functools import partial

from PyQt5 import QtCore, QtGui, QtWidgets
import h5py

from artiq import __artiq_dir__ as artiq_dir
from artiq.gui.tools import LayoutWidget, log_level_to_name
from artiq.gui.entries import argty_to_entry
from artiq.protocols import pyon


logger = logging.getLogger(__name__)


class _WheelFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if (event.type() == QtCore.QEvent.Wheel and
                event.modifiers() != QtCore.Qt.NoModifier):
            event.ignore()
            return True
        return False


class _ArgumentEditor(QtWidgets.QTreeWidget):
    def __init__(self, expurl):
        QtWidgets.QTreeWidget.__init__(self)
        self.setColumnCount(3)
        self.header().setStretchLastSection(False)
        if hasattr(self.header(), "setSectionResizeMode"):
            set_resize_mode = self.header().setSectionResizeMode
        else:
            set_resize_mode = self.header().setResizeMode
        set_resize_mode(0, QtWidgets.QHeaderView.ResizeToContents)
        set_resize_mode(1, QtWidgets.QHeaderView.Stretch)
        set_resize_mode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.header().setVisible(False)
        self.setSelectionMode(self.NoSelection)
        self.setHorizontalScrollMode(self.ScrollPerPixel)
        self.setVerticalScrollMode(self.ScrollPerPixel)

        self.viewport().installEventFilter(_WheelFilter(self.viewport()))

        self.expurl = expurl

        self._groups = dict()
        self._arg_to_entry_widgetitem = dict()

        arguments = self.get_submission_arguments()  # TODO

        if not arguments:
            self.addTopLevelItem(QtWidgets.QTreeWidgetItem(["No arguments"]))

        for name, argument in arguments.items():
            entry = argty_to_entry[argument["desc"]["ty"]](argument)
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
        buttons.layout.setColumnStretch(0, 1)
        buttons.layout.setColumnStretch(1, 0)
        buttons.layout.setColumnStretch(2, 0)
        buttons.layout.setColumnStretch(3, 1)
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

    def get_submission_arguments(self):
        return {}  # TODO

    def _recompute_arguments_clicked(self):
        pass  # TODO

    def _recompute_argument_clicked(self, name):
        asyncio.ensure_future(self._recompute_argument(name))

    async def _recompute_argument(self, name):
        try:
            arginfo = await self.compute_arginfo()
        except:
            logger.error("Could not recompute argument '%s' of '%s'",
                         name, self.expurl, exc_info=True)
            return
        argument = self.get_submission_arguments()[name]

        procdesc = arginfo[name][0]
        state = argty_to_entry[procdesc["ty"]].default_state(procdesc)
        argument["desc"] = procdesc
        argument["state"] = state

        old_entry, widget_item = self._arg_to_entry_widgetitem[name]
        old_entry.deleteLater()

        entry = argty_to_entry[procdesc["ty"]](argument)
        self._arg_to_entry_widgetitem[name] = entry, widget_item
        self.setItemWidget(widget_item, 1, entry)

    async def compute_arginfo(self):
        return {}  # TODO

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

    def __init__(self, expurl):
        QtWidgets.QMdiSubWindow.__init__(self)
        self.setWindowTitle(expurl)
        self.setWindowIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_FileDialogContentsView))

        self.layout = QtWidgets.QGridLayout()
        top_widget = QtWidgets.QWidget()
        top_widget.setLayout(self.layout)
        self.setWidget(top_widget)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.expurl = expurl

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

        await self._recompute_arguments_task(arguments)

    def closeEvent(self, event):
        self.sigClosed.emit()
        QtWidgets.QMdiSubWindow.closeEvent(self, event)

    def save_state(self):
        return {
            "argeditor": self.argeditor.save_state(),
            "geometry": bytes(self.saveGeometry()),
            "expurl": self.expurl,
            "options": self.options,
        }

    def restore_state(self, state):
        self.argeditor.restore_state(state["argeditor"])
        self.restoreGeometry(QtCore.QByteArray(state["geometry"]))
        self.expurl = state["expurl"]
        self.options = state["options"]


class ExperimentsArea(QtWidgets.QMdiArea):
    def __init__(self, root):
        QtWidgets.QMdiArea.__init__(self)
        self.pixmap = QtGui.QPixmap(os.path.join(
            artiq_dir, "gui", "logo20.svg"))
        self.current_dir = root
        self.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        action = QtWidgets.QAction("&Open experiment", self)
        action.setShortcut(QtGui.QKeySequence("CTRL+o"))
        action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        action.triggered.connect(self.open_experiment)
        self.addAction(action)

        self.open_experiments = []

    def paintEvent(self, event):
        QtWidgets.QMdiArea.paintEvent(self, event)
        painter = QtGui.QPainter(self.viewport())
        x = (self.width() - self.pixmap.width())//2
        y = (self.height() - self.pixmap.height())//2
        painter.setOpacity(0.5)
        painter.drawPixmap(x, y, self.pixmap)

    def save_state(self):
        return {"experiments": [experiment.save_state()
                                for experiment in self.open_experiments]}

    def restore_state(self, state):
        if self.open_experiments:
            raise NotImplementedError
        for ex_state in state["experiments"]:
            ex = self.load_experiment(ex_state["expurl"])
            ex.restore_state(ex_state)

    def open_experiment(self):
        file, filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open experiment", self.current_dir, "Experiments (*.py)")
        if not file:
            return
        logger.info("opening experiment %s", file)
        self.load_experiment(file)

    def load_experiment(self, expurl):
        try:
            dock = _ExperimentDock(expurl)
        except:
            logger.warning("Failed to create experiment dock for %s, "
                           "attempting to reset arguments", expurl,
                           exc_info=True)
            del self.submission_arguments[expurl]
            dock = _ExperimentDock(expurl)
        self.open_experiments.append(dock)
        self.addSubWindow(dock)
        dock.show()
        dock.sigClosed.connect(partial(self.on_dock_closed, expurl))
        return dock

    def on_dock_closed(self, expurl):
        del self.open_experiments[expurl]
