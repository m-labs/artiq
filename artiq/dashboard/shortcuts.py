import logging
from functools import partial

from PyQt5 import QtCore, QtWidgets

from artiq.gui.tools import LayoutWidget


logger = logging.getLogger(__name__)


class ShortcutsDock(QtWidgets.QDockWidget):
    def __init__(self, main_window, exp_manager):
        QtWidgets.QDockWidget.__init__(self, "Shortcuts")
        self.setObjectName("Shortcuts")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        layout = QtWidgets.QGridLayout()
        top_widget = QtWidgets.QWidget()
        top_widget.setLayout(layout)
        self.setWidget(top_widget)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        self.exp_manager = exp_manager
        self.shortcut_widgets = dict()

        for n, title in enumerate(["Key", "Experiment"]):
            label = QtWidgets.QLabel("<b>" + title + "</b>")
            layout.addWidget(label, 0, n)
            label.setMaximumHeight(label.sizeHint().height())
        layout.setColumnStretch(1, 1)

        for i in range(12):
            row = i + 1

            layout.addWidget(QtWidgets.QLabel("F" + str(i+1)), row, 0)

            label = QtWidgets.QLabel()
            label.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                QtWidgets.QSizePolicy.Ignored)
            layout.addWidget(label, row, 1)

            clear = QtWidgets.QToolButton()
            clear.setIcon(QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DialogDiscardButton))
            layout.addWidget(clear, row, 2)
            clear.clicked.connect(partial(self.set_shortcut, i, ""))

            open = QtWidgets.QToolButton()
            open.setIcon(QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DialogOpenButton))
            layout.addWidget(open, row, 3)
            open.clicked.connect(partial(self._open_experiment, i))

            submit = QtWidgets.QPushButton("Submit")
            submit.setIcon(QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DialogOkButton))
            layout.addWidget(submit, row, 4)
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
            shortcut = QtWidgets.QShortcut("F" + str(i+1), main_window)
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
