#!/usr/bin/env python3

from PyQt5 import QtWidgets, QtCore, QtGui
from artiq.applets.simple import SimpleApplet


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


class NumberWidget(QtWidgets.QStackedWidget):
    def __init__(self, args, req):
        QtWidgets.QStackedWidget.__init__(self)
        self.dataset_name = args.dataset
        self.req = req

        self.lcd_widget = QResponsiveLCDNumber()
        self.lcd_widget.setDigitCount(args.digit_count)
        self.lcd_widget.doubleClicked.connect(self.start_edit)
        self.addWidget(self.lcd_widget)

        self.edit_widget = QCancellableLineEdit()
        self.edit_widget.setValidator(QtGui.QDoubleValidator())
        self.edit_widget.setAlignment(QtCore.Qt.AlignRight)
        self.edit_widget.editCancelled.connect(self.cancel_edit)
        self.edit_widget.returnPressed.connect(self.confirm_edit)
        self.addWidget(self.edit_widget)

        font = QtGui.QFont()
        font.setPointSize(60)
        self.edit_widget.setFont(font)

        self.setCurrentWidget(self.lcd_widget)

    def start_edit(self):
        # QLCDNumber value property contains the value of zero
        # if the displayed value is not a number.
        self.edit_widget.setText(str(self.lcd_widget.value()))
        self.edit_widget.selectAll()
        self.edit_widget.setFocus()
        self.setCurrentWidget(self.edit_widget)

    def confirm_edit(self):
        value = float(self.edit_widget.text())
        self.req.set_dataset(self.dataset_name, value)
        self.setCurrentWidget(self.lcd_widget)

    def cancel_edit(self):
        self.setCurrentWidget(self.lcd_widget)

    def data_changed(self, value, metadata, persist, mods):
        try:
            n = float(value[self.dataset_name])
        except (KeyError, ValueError, TypeError):
            n = "---"
        self.lcd_widget.display(n)


def main():
    applet = SimpleApplet(NumberWidget)
    applet.add_dataset("dataset", "dataset to show")
    applet.argparser.add_argument("--digit-count", type=int, default=10,
                                  help="total number of digits to show")
    applet.run()

if __name__ == "__main__":
    main()
