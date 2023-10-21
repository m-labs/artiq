import asyncio
import logging

from PyQt6 import QtCore, QtWidgets


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


class WheelFilter(QtCore.QObject):
    def __init__(self, parent, ignore_with_modifier=False):
        super().__init__(parent)
        self.ignore_with_modifier = ignore_with_modifier

    def eventFilter(self, obj, event):
        if event.type() != QtCore.QEvent.Type.Wheel:
            return False
        has_modifier = event.modifiers() != QtCore.Qt.KeyboardModifier.NoModifier
        if has_modifier == self.ignore_with_modifier:
            event.ignore()
            return True
        return False


def disable_scroll_wheel(widget):
    widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    widget.installEventFilter(WheelFilter(widget))


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
    dialog.setFileMode(dialog.FileMode.ExistingFile)
    dialog.setAcceptMode(dialog.AcceptMode.AcceptOpen)
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
        regexp = self.filterRegularExpression()
        if not regexp.isEmpty():
            source_index = self.sourceModel().index(
                source_row, self.filterKeyColumn(), source_parent)
            if source_index.isValid():
                for i in range(self.sourceModel().rowCount(source_index)):
                    if self.filterAcceptsRow(i, source_index):
                        return True
                key = self.sourceModel().data(source_index, self.filterRole())
                return regexp.match(key).hasMatch()
        return QtCore.QSortFilterProxyModel.filterAcceptsRow(
            self, source_row, source_parent)
