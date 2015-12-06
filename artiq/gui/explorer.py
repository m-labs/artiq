import asyncio
import logging
from functools import partial

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.gui.models import DictSyncTreeSepModel


class Model(DictSyncTreeSepModel):
    def __init__(self, init):
        self.explorer = None
        DictSyncTreeSepModel.__init__(self, "/", ["Experiment"], init)

    def __setitem__(self, k, v):
        DictSyncTreeSepModel.__setitem__(self, k, v)
        # TODO
        #if self.explorer is not None and k == self.explorer.selected_key:
        #    self.explorer.update_selection(k, k)


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
        self.el.doubleClicked.connect(self.open_clicked)

        open = QtGui.QPushButton("Open")
        open.setIcon(QtGui.QApplication.style().standardIcon(
            QtGui.QStyle.SP_DialogOpenButton))
        open.setToolTip("Open the selected experiment (Return)")
        self.addWidget(open, 1, 0)
        open.clicked.connect(self.open_clicked)

        submit = QtGui.QPushButton("Submit")
        submit.setIcon(QtGui.QApplication.style().standardIcon(
            QtGui.QStyle.SP_DialogOkButton))
        submit.setToolTip("Schedule the selected experiment (Ctrl+Return)")
        self.addWidget(submit, 1, 1)
        submit.clicked.connect(self.submit_clicked)

        self.explist_model = Model(dict())
        explist_sub.add_setmodel_callback(self.set_model)

        self.el.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        open_action = QtGui.QAction("Open", self.el)
        open_action.triggered.connect(self.open_clicked)
        open_action.setShortcut("RETURN")
        self.el.addAction(open_action)
        submit_action = QtGui.QAction("Submit", self.el)
        submit_action.triggered.connect(self.submit_clicked)
        submit_action.setShortcut("CTRL+RETURN")
        self.el.addAction(submit_action)
        reqterm_action = QtGui.QAction("Request termination of instances", self.el)
        reqterm_action.triggered.connect(self.reqterm_clicked)
        reqterm_action.setShortcut("CTRL+BACKSPACE")
        self.el.addAction(reqterm_action)

        sep = QtGui.QAction(self.el)
        sep.setSeparator(True)
        self.el.addAction(sep)

        set_shortcut_menu = QtGui.QMenu()
        for i in range(12):
            action = QtGui.QAction("F" + str(i+1), self.el)
            action.triggered.connect(partial(self.set_shortcut, i))
            set_shortcut_menu.addAction(action)

        set_shortcut_action = QtGui.QAction("Set shortcut", self.el)
        set_shortcut_action.setMenu(set_shortcut_menu)
        self.el.addAction(set_shortcut_action)
        scan_repository_action = QtGui.QAction("(Re)scan repository HEAD",
                                               self.el)
        def scan_repository():
            asyncio.ensure_future(experiment_db_ctl.scan_repository_async())
            self.status_bar.showMessage("Requested repository scan")
        scan_repository_action.triggered.connect(scan_repository)
        self.el.addAction(scan_repository_action)

    def set_model(self, model):
        model.explorer = self
        self.explist_model = model
        self.el.setModel(model)

    def _get_selected_expname(self):
        selection = self.el.selectedIndexes()
        if selection:
            return self.explist_model.index_to_key(selection[0])
        else:
            return None

    def open_clicked(self):
        expname = self._get_selected_expname()
        if expname is not None:
            self.exp_manager.open_experiment(expname)

    def submit_clicked(self):
        expname = self._get_selected_expname()
        if expname is not None:
            self.exp_manager.submit(expname)

    def reqterm_clicked(self):
        expname = self._get_selected_expname()
        if expname is not None:
            self.exp_manager.request_inst_term(expname)

    def set_shortcut(self, nr):
        expname = self._get_selected_expname()
        if expname is not None:
            self.d_shortcuts.set_shortcut(nr, expname)
