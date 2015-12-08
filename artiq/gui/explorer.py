import asyncio
import logging
from functools import partial

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.gui.models import DictSyncTreeSepModel


class _OpenFileDialog(QtGui.QDialog):
    def __init__(self, parent, exp_manager):
        QtGui.QDialog.__init__(self, parent=parent)
        self.setWindowTitle("Open file outside repository")

        grid = QtGui.QGridLayout()
        self.setLayout(grid)

        grid.addWidget(QtGui.QLabel("Filename:"), 0, 0)
        filename = QtGui.QLineEdit()
        grid.addWidget(filename, 0, 1)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        grid.addWidget(buttons, 1, 0, 1, 2)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        def open_file():
            file = filename.text()
            asyncio.ensure_future(exp_manager.open_file(file))
        self.accepted.connect(open_file)


class Model(DictSyncTreeSepModel):
    def __init__(self, init):
        DictSyncTreeSepModel.__init__(self, "/", ["Experiment"], init)


class ExplorerDock(dockarea.Dock):
    def __init__(self, status_bar, exp_manager, d_shortcuts,
                 explist_sub, schedule_ctl, experiment_db_ctl):
        dockarea.Dock.__init__(self, "Explorer", size=(1500, 500))
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.status_bar = status_bar
        self.exp_manager = exp_manager
        self.d_shortcuts = d_shortcuts
        self.schedule_ctl = schedule_ctl

        self.el = QtGui.QTreeView()
        self.el.setHeaderHidden(True)
        self.el.setSelectionBehavior(QtGui.QAbstractItemView.SelectItems)
        self.addWidget(self.el, 0, 0, colspan=2)
        self.el.doubleClicked.connect(
            partial(self.expname_action, "open_experiment"))

        open = QtGui.QPushButton("Open")
        open.setIcon(QtGui.QApplication.style().standardIcon(
            QtGui.QStyle.SP_DialogOpenButton))
        open.setToolTip("Open the selected experiment (Return)")
        self.addWidget(open, 1, 0)
        open.clicked.connect(
            partial(self.expname_action, "open_experiment"))

        submit = QtGui.QPushButton("Submit")
        submit.setIcon(QtGui.QApplication.style().standardIcon(
            QtGui.QStyle.SP_DialogOkButton))
        submit.setToolTip("Schedule the selected experiment (Ctrl+Return)")
        self.addWidget(submit, 1, 1)
        submit.clicked.connect(
            partial(self.expname_action, "submit"))

        self.explist_model = Model(dict())
        explist_sub.add_setmodel_callback(self.set_model)

        self.el.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        open_action = QtGui.QAction("Open", self.el)
        open_action.triggered.connect(
            partial(self.expname_action, "open_experiment"))
        open_action.setShortcut("RETURN")
        self.el.addAction(open_action)
        submit_action = QtGui.QAction("Submit", self.el)
        submit_action.triggered.connect(
            partial(self.expname_action, "submit"))
        submit_action.setShortcut("CTRL+RETURN")
        self.el.addAction(submit_action)
        reqterm_action = QtGui.QAction("Request termination of instances", self.el)
        reqterm_action.triggered.connect(
            partial(self.expname_action, "request_inst_term"))
        reqterm_action.setShortcut("CTRL+BACKSPACE")
        self.el.addAction(reqterm_action)

        set_shortcut_menu = QtGui.QMenu()
        for i in range(12):
            action = QtGui.QAction("F" + str(i+1), self.el)
            action.triggered.connect(partial(self.set_shortcut, i))
            set_shortcut_menu.addAction(action)

        set_shortcut_action = QtGui.QAction("Set shortcut", self.el)
        set_shortcut_action.setMenu(set_shortcut_menu)
        self.el.addAction(set_shortcut_action)

        sep = QtGui.QAction(self.el)
        sep.setSeparator(True)
        self.el.addAction(sep)

        scan_repository_action = QtGui.QAction("Scan repository HEAD",
                                               self.el)
        def scan_repository():
            asyncio.ensure_future(experiment_db_ctl.scan_repository_async())
            self.status_bar.showMessage("Requested repository scan")
        scan_repository_action.triggered.connect(scan_repository)
        self.el.addAction(scan_repository_action)

        open_file_action = QtGui.QAction("Open file outside repository",
                                         self.el)
        open_file_action.triggered.connect(
            lambda: _OpenFileDialog(self, self.exp_manager).open())
        self.el.addAction(open_file_action)

    def set_model(self, model):
        self.explist_model = model
        self.el.setModel(model)

    def _get_selected_expname(self):
        selection = self.el.selectedIndexes()
        if selection:
            return self.explist_model.index_to_key(selection[0])
        else:
            return None

    def expname_action(self, action):
        expname = self._get_selected_expname()
        if expname is not None:
            action = getattr(self.exp_manager, action)
            action("repo:" + expname)

    def set_shortcut(self, nr):
        expname = self._get_selected_expname()
        if expname is not None:
            expurl = "repo:" + expname
            self.d_shortcuts.set_shortcut(nr, expurl)
            self.status_bar.showMessage("Set shortcut F{} to '{}'"
                                        .format(nr+1, expurl))
