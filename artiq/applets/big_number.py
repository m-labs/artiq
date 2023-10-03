#!/usr/bin/env python3
import re
import logging
import numpy as np

from PyQt5 import QtWidgets, QtCore, QtGui

from artiq.language import units
from artiq.tools import short_format, scale_from_metadata
from artiq.applets.simple import SimpleApplet


class QResponsiveLabel(QtWidgets.QLabel):
    doubleClicked = QtCore.pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()


class QCancellableLineEdit(QtWidgets.QLineEdit):
    editCancelled = QtCore.pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.editCancelled.emit()
        else:
            super().keyPressEvent(event)


class NumberWidget(QtWidgets.QStackedWidget):
    def __init__(self, args, ctl):
        QtWidgets.QStackedWidget.__init__(self)
        self.dataset_name = args.dataset
        self.ctl = ctl
        self.value = None
        self.metadata = {}

        font = QtGui.QFont()
        font.setPointSize(60)

        self.display_widget = QResponsiveLabel()
        self.display_widget.setFont(font)
        self.display_widget.setAlignment(
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.display_widget.doubleClicked.connect(self.start_edit)
        self.addWidget(self.display_widget)

        self.edit_widget = QCancellableLineEdit()
        self.edit_widget.setFont(font)
        self.edit_widget.setAlignment(
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.edit_widget.editCancelled.connect(
            lambda: self.setCurrentWidget(self.display_widget))
        self.edit_widget.returnPressed.connect(self.confirm_edit)
        self.addWidget(self.edit_widget)

        input_regexp = r"(([+-]?\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)"
        self.regexp = "^" + input_regexp + r"( [a-zA-Z]*)?$"

        self.setCurrentWidget(self.display_widget)

    def start_edit(self):
        if self.value is None:
            self.edit_widget.setText("---")
        else:
            unit = self.metadata.get("unit", "")
            scale = int(scale_from_metadata(self.metadata))
            if scale == 1.0:
                scale = int(scale)
            if isinstance(self.value, int) and isinstance(scale, int):
                value = self.value//scale
            else:
                value = self.value / scale
            self.edit_widget.setText(f"{value} {unit}".strip())
        self.edit_widget.selectAll()
        self.edit_widget.setFocus()
        self.setCurrentWidget(self.edit_widget)

    def confirm_edit(self):
        entry = re.match(self.regexp, self.edit_widget.text())
        if entry is not None:
            value = entry.group(1)
            if np.issubdtype(self.type, np.integer):
                value = self.type(int(float(value))) 
            elif np.issubdtype(self.type, np.floating):
                value = self.type(value)
            elif self.type in [int, float]:
               value = self.type(float(value)) 
            else:
                logging.warning("Unsupported data type:", self.type)
                return
            unit = entry.group(5).strip() if entry.group(5) else ""
            scale = scale_from_metadata(self.metadata)
            if scale == 1.0:
                scale = int(scale)
            precision = self.metadata.get("precision")
            self.ctl.set_dataset(self.dataset_name, value*scale, 
                                unit, scale, precision)
            self.setCurrentWidget(self.display_widget)
        else:
            self.setCurrentWidget(self.display_widget)
            

    def data_changed(self, value, metadata, persist, mods):
        self.metadata = metadata.get(self.dataset_name, {})
        try:
            self.value = value[self.dataset_name]
            self.type = type(self.value)
            n = short_format(self.value, self.metadata)
        except (KeyError, ValueError, TypeError):
            n = "---"
        self.display_widget.setText(n)


def main():
    applet = SimpleApplet(NumberWidget)
    applet.add_dataset("dataset", "dataset to show")
    applet.run()

if __name__ == "__main__":
    main()
