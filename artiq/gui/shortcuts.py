import logging
from functools import partial

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
try:
    from quamash import QtWidgets
    QShortcut = QtWidgets.QShortcut
except:
    QShortcut = QtGui.QShortcut


logger = logging.getLogger(__name__)


class ShortcutsDock(dockarea.Dock):
    def __init__(self, main_window, exp_manager):
        dockarea.Dock.__init__(self, "Shortcuts", size=(1000, 300))
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.exp_manager = exp_manager
        self.shortcut_widgets = dict()

        for n, title in enumerate(["Key", "Experiment"]):
            label = QtGui.QLabel("<b>" + title + "</b>")
            self.addWidget(label, 0, n)
            label.setMaximumHeight(label.sizeHint().height())
        self.layout.setColumnStretch(1, 1)

        for i in range(12):
            row = i + 1

            self.addWidget(QtGui.QLabel("F" + str(i+1)), row, 0)

            label = QtGui.QLabel()
            label.setSizePolicy(QtGui.QSizePolicy.Ignored,
                                QtGui.QSizePolicy.Ignored)
            self.addWidget(label, row, 1)

            clear = QtGui.QToolButton()
            clear.setIcon(QtGui.QApplication.style().standardIcon(
                QtGui.QStyle.SP_DialogResetButton))
            self.addWidget(clear, row, 2)
            clear.clicked.connect(partial(self.set_shortcut, i, ""))

            open = QtGui.QToolButton()
            open.setIcon(QtGui.QApplication.style().standardIcon(
                QtGui.QStyle.SP_DialogOpenButton))
            self.addWidget(open, row, 3)
            open.clicked.connect(partial(self._open_experiment, i))

            submit = QtGui.QPushButton("Submit")
            submit.setIcon(QtGui.QApplication.style().standardIcon(
                QtGui.QStyle.SP_DialogOkButton))
            self.addWidget(submit, row, 4)
            submit.clicked.connect(partial(self._activated, i))

            clear.hide()
            open.hide()
            submit.hide()

            self.shortcut_widgets[i] = {
                "label": label,
                "clear": clear,
                "open": open,
                "submit": submit
            }
            shortcut = QShortcut("F" + str(i+1), main_window)
            shortcut.setContext(QtCore.Qt.ApplicationShortcut)
            shortcut.activated.connect(partial(self._activated, i))

    def _activated(self, nr):
        expurl = self.shortcut_widgets[nr]["label"].text()
        if expurl:
            try:
                self.exp_manager.submit(expurl)
            except:
                # May happen when experiment has been removed
                # from repository/explist
                logger.warning("failed to submit experiment %s",
                               expurl, exc_info=True)

    def _open_experiment(self, nr):
        expurl = self.shortcut_widgets[nr]["label"].text()
        if expurl:
            try:
                self.exp_manager.open_experiment(expurl)
            except:
                # May happen when experiment has been removed
                # from repository/explist
                logger.warning("failed to open experiment %s",
                               expurl, exc_info=True)

    def set_shortcut(self, nr, expurl):
        widgets = self.shortcut_widgets[nr]
        widgets["label"].setText(expurl)
        if expurl:
            widgets["clear"].show()
            widgets["open"].show()
            widgets["submit"].show()
        else:
            widgets["clear"].hide()
            widgets["open"].hide()
            widgets["submit"].hide()

    def save_state(self):
        return {nr: widgets["label"].text()
                for nr, widgets in self.shortcut_widgets.items()}

    def restore_state(self, state):
        for nr, expurl in state.items():
            self.set_shortcut(nr, expurl)
