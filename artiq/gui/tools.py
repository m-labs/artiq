import asyncio
import logging

from PyQt6 import QtCore, QtGui, QtWidgets


class DoubleClickLineEdit(QtWidgets.QLineEdit):
    finished = QtCore.pyqtSignal()

    def __init__(self, init):
        QtWidgets.QLineEdit.__init__(self, init)
        self.setFrame(False)
        self.setReadOnly(True)
        self.returnPressed.connect(self._return_pressed)
        self.editingFinished.connect(self._editing_finished)
        self._text = init

    def mouseDoubleClickEvent(self, event):
        if self.isReadOnly():
            self.setReadOnly(False)
            self.setFrame(True)
        QtWidgets.QLineEdit.mouseDoubleClickEvent(self, event)

    def _return_pressed(self):
        self._text = self.text()

    def _editing_finished(self):
        self.setReadOnly(True)
        self.setFrame(False)
        self.setText(self._text)
        self.finished.emit()

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Escape and not self.isReadOnly():
            self.editingFinished.emit()
        else:
            QtWidgets.QLineEdit.keyPressEvent(self, event)


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


class SelectableColumnTableView(QtWidgets.QTableView):
    """A QTableView packaged up with a header row context menu that allows users to
    show/hide columns using checkable entries.

    By default, all columns are shown. If only one shown column remains, the entry is
    disabled to prevent a situation where no columns are shown, which might be confusing
    to the user.

    Qt considers whether columns are shown to be part of the header state, i.e. it is
    included in saveState()/restoreState().
    """

    def __init__(self):
        super().__init__()

        self.horizontalHeader().setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(
            self.show_header_context_menu)

    def show_header_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)

        num_columns_total = self.model().columnCount()
        num_columns_shown = sum(
            (not self.isColumnHidden(i)) for i in range(num_columns_total))
        for i in range(num_columns_total):
            name = self.model().headerData(i, QtCore.Qt.Orientation.Horizontal)
            action = QtGui.QAction(name, self)
            action.setCheckable(True)

            is_currently_hidden = self.isColumnHidden(i)
            action.setChecked(not is_currently_hidden)
            if not is_currently_hidden:
                if num_columns_shown == 1:
                    # Don't allow hiding of the last visible column.
                    action.setEnabled(False)

            action.triggered.connect(
                lambda checked, i=i: self.setColumnHidden(i, not checked))
            menu.addAction(action)

        menu.exec(self.horizontalHeader().mapToGlobal(pos))


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


async def get_save_file_name(parent, caption, dir, filter, suffix=None):
    """like QtWidgets.QFileDialog.getSaveFileName(), but a coroutine"""
    dialog = QtWidgets.QFileDialog(parent, caption, dir, filter)
    dialog.setFileMode(dialog.AnyFile)
    dialog.setAcceptMode(dialog.AcceptSave)
    if suffix is not None:
        dialog.setDefaultSuffix(suffix)
    fut = asyncio.Future()

    def on_accept():
        fut.set_result(dialog.selectedFiles()[0])
    dialog.accepted.connect(on_accept)
    dialog.rejected.connect(fut.cancel)
    dialog.open()
    return await fut

