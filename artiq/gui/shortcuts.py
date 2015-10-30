from functools import partial

from quamash import QtGui
try:
    from quamash import QtWidgets
    QShortcut = QtWidgets.QShortcut
except:
    QShortcut = QtGui.QShortcut


class _ShortcutEditor(QtGui.QDialog):
    def __init__(self, parent, experiments, shortcuts):
        QtGui.QDialog.__init__(self, parent=parent)
        self.setWindowTitle("Shortcuts")

        self.shortcuts = shortcuts
        self.edit_widgets = dict()

        grid = QtGui.QGridLayout()
        self.setLayout(grid)

        for n, title in enumerate(["Key", "Experiment", "Priority", "Pipeline"]):
            label = QtGui.QLabel("<b>" + title + "</b")
            grid.addWidget(label, 0, n)
            label.setMaximumHeight(label.sizeHint().height())
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        for i in range(12):
            row = i + 1
            existing_shortcut = self.shortcuts.get(i, dict())

            grid.addWidget(QtGui.QLabel("F" + str(i+1)), row, 0)

            experiment = QtGui.QComboBox()
            grid.addWidget(experiment, row, 1)
            experiment.addItem("<None>")
            experiment.addItems(experiments)
            experiment.setEditable(True)
            experiment.setEditText(
                existing_shortcut.get("experiment", "<None>"))
            
            priority = QtGui.QSpinBox()
            grid.addWidget(priority, row, 2)
            priority.setRange(-99, 99)
            priority.setValue(existing_shortcut.get("priority", 0))

            pipeline = QtGui.QLineEdit()
            grid.addWidget(pipeline, row, 3)
            pipeline.setText(existing_shortcut.get("pipeline", "main"))

            self.edit_widgets[i] = {
                "experiment": experiment,
                "priority": priority,
                "pipeline": pipeline
            }

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        grid.addWidget(buttons, 14, 0, 1, 4)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.accepted.connect(self.on_accept)

    def on_accept(self):
        for n, widgets in self.edit_widgets.items():
            self.shortcuts[n] = {
                "experiment": widgets["experiment"].currentText(),
                "priority": widgets["priority"].value(),
                "pipeline": widgets["pipeline"].text()
            }


class ShortcutManager:
    def __init__(self, main_window, explorer):
        for i in range(12):
            shortcut = QShortcut("F" + str(i+1), main_window)
            shortcut.activated.connect(partial(self._activated, i))
        self.main_window = main_window
        self.explorer = explorer
        self.shortcuts = dict()

    def edit(self, experiments):
        dlg = _ShortcutEditor(self.main_window, experiments, self.shortcuts)
        dlg.open()

    def _activated(self, nr):
        info = self.shortcuts.get(nr, dict())
        experiment = info.get("experiment", "")
        if experiment and experiment != "<None>":
            self.explorer.submit(info["pipeline"], experiment,
                                 info["priority"], None, False)

    def save_state(self):
        return self.shortcuts

    def restore_state(self, state):
        self.shortcuts = state
