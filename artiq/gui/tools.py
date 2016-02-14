import logging

from PyQt5 import QtCore, QtWidgets, QtGui


def log_level_to_name(level):
    if level >= logging.CRITICAL:
        return "CRITICAL"
    if level >= logging.ERROR:
        return "ERROR"
    if level >= logging.WARNING:
        return "WARNING"
    if level >= logging.INFO:
        return "INFO"
    return "DEBUG"


class _WheelFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Wheel:
            event.ignore()
            return True
        else:
            return False


def disable_scroll_wheel(widget):
    widget.setFocusPolicy(QtCore.Qt.StrongFocus)
    widget.installEventFilter(_WheelFilter(widget))


class QDockWidgetCloseDetect(QtWidgets.QDockWidget):
    sigClosed = QtCore.pyqtSignal()

    def closeEvent(self, event):
        self.sigClosed.emit()
        QtWidgets.QDockWidget.closeEvent(self, event)
