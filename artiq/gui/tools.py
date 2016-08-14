import asyncio
import logging

from PyQt5 import QtCore, QtWidgets


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
        if (event.type() == QtCore.QEvent.Wheel and
                event.modifiers() == QtCore.Qt.NoModifier):
            event.ignore()
            return True
        return False


def disable_scroll_wheel(widget):
    widget.setFocusPolicy(QtCore.Qt.StrongFocus)
    widget.installEventFilter(_WheelFilter(widget))


class QDockWidgetCloseDetect(QtWidgets.QDockWidget):
    sigClosed = QtCore.pyqtSignal()

    def closeEvent(self, event):
        self.sigClosed.emit()
        QtWidgets.QDockWidget.closeEvent(self, event)


class LayoutWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

    def addWidget(self, item, row=0, col=0, rowspan=1, colspan=1):
        self.layout.addWidget(item, row, col, rowspan, colspan)


async def get_open_file_name(parent, caption, dir, filter):
    """like QtWidgets.QFileDialog.getOpenFileName(), but a coroutine"""
    dialog = QtWidgets.QFileDialog(parent, caption, dir, filter)
    dialog.setFileMode(dialog.ExistingFile)
    dialog.setAcceptMode(dialog.AcceptOpen)
    fut = asyncio.Future()

    def on_accept():
        fut.set_result(dialog.selectedFiles()[0])
    dialog.accepted.connect(on_accept)
    dialog.rejected.connect(fut.cancel)
    dialog.open()
    return await fut


# Based on:
# http://stackoverflow.com/questions/250890/using-qsortfilterproxymodel-with-a-tree-model
class QRecursiveFilterProxyModel(QtCore.QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        regexp = self.filterRegExp()
        if not regexp.isEmpty():
            source_index = self.sourceModel().index(
                source_row, self.filterKeyColumn(), source_parent)
            if source_index.isValid():
                for i in range(self.sourceModel().rowCount(source_index)):
                    if self.filterAcceptsRow(i, source_index):
                        return True
                key = self.sourceModel().data(source_index, self.filterRole())
                return regexp.indexIn(key) != -1
        return QtCore.QSortFilterProxyModel.filterAcceptsRow(
            self, source_row, source_parent)
