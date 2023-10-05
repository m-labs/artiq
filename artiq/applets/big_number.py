#!/usr/bin/env python3

from PyQt5 import QtWidgets, QtCore, QtGui
from artiq.applets.simple import SimpleApplet
from artiq.tools import scale_from_metadata
from artiq.gui.tools import LayoutWidget


class QResponsiveLCDNumber(QtWidgets.QLCDNumber):
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


class NumberWidget(LayoutWidget):
    def __init__(self, args, req):
        LayoutWidget.__init__(self)
        self.dataset_name = args.dataset
        self.req = req
        self.metadata = dict()

        self.number_area = QtWidgets.QStackedWidget()
        self.addWidget(self.number_area, 0, 0)

        self.unit_area = QtWidgets.QLabel()
        self.unit_area.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        self.addWidget(self.unit_area, 0, 1)

        self.lcd_widget = QResponsiveLCDNumber()
        self.lcd_widget.setDigitCount(args.digit_count)
        self.lcd_widget.doubleClicked.connect(self.start_edit)
        self.number_area.addWidget(self.lcd_widget)

        self.edit_widget = QCancellableLineEdit()
        self.edit_widget.setValidator(QtGui.QDoubleValidator())
        self.edit_widget.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.edit_widget.editCancelled.connect(self.cancel_edit)
        self.edit_widget.returnPressed.connect(self.confirm_edit)
        self.number_area.addWidget(self.edit_widget)

        font = QtGui.QFont()
        font.setPointSize(60)
        self.edit_widget.setFont(font)

        unit_font = QtGui.QFont()
        unit_font.setPointSize(20)
        self.unit_area.setFont(unit_font)

        self.number_area.setCurrentWidget(self.lcd_widget)

    def start_edit(self):
        # QLCDNumber value property contains the value of zero
        # if the displayed value is not a number.
        self.edit_widget.setText(str(self.lcd_widget.value()))
        self.edit_widget.selectAll()
        self.edit_widget.setFocus()
        self.number_area.setCurrentWidget(self.edit_widget)

    def confirm_edit(self):
        scale = scale_from_metadata(self.metadata)
        val = float(self.edit_widget.text())
        val *= scale
        self.req.set_dataset(self.dataset_name, val, **self.metadata)
        self.number_area.setCurrentWidget(self.lcd_widget)

    def cancel_edit(self):
        self.number_area.setCurrentWidget(self.lcd_widget)

    def data_changed(self, value, metadata, persist, mods):
        try:
            self.metadata = metadata[self.dataset_name]
            # This applet will degenerate other scalar types to native float on edit
            # Use the dashboard ChangeEditDialog for consistent type casting 
            val = float(value[self.dataset_name])
            scale = scale_from_metadata(self.metadata)
            val /= scale
        except (KeyError, ValueError, TypeError):
            val = "---"
        
        unit = self.metadata.get("unit", "")
        self.unit_area.setText(unit)
        self.lcd_widget.display(val)


def main():
    applet = SimpleApplet(NumberWidget)
    applet.add_dataset("dataset", "dataset to show")
    applet.argparser.add_argument("--digit-count", type=int, default=10,
                                  help="total number of digits to show")
    applet.run()

if __name__ == "__main__":
    main()
