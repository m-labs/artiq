from PyQt5 import QtCore, QtWidgets, QtGui

from artiq.gui.flowlayout import FlowLayout


class VDragDropSplitter(QtWidgets.QSplitter):
    dropped = QtCore.pyqtSignal(int, int)

    def __init__(self, parent):
        QtWidgets.QSplitter.__init__(self, parent=parent)
        self.setAcceptDrops(True)
        self.setContentsMargins(0, 0, 0, 0)
        self.setOrientation(QtCore.Qt.Vertical)
        self.setChildrenCollapsible(False)

    def resetSizes(self):
        self.setSizes(self.count() * [1])

    def dragEnterEvent(self, e):
        e.accept()

    def dragLeaveEvent(self, e):
        self.setRubberBand(-1)
        e.accept()

    def dragMoveEvent(self, e):
        pos = e.pos()
        src = e.source()
        src_i = self.indexOf(src)
        self.setRubberBand(self.height())
        # case 0: smaller than source widget
        if pos.y() < src.y():
            for n in range(src_i):
                w = self.widget(n)
                if pos.y() < w.y() + w.size().height():
                    self.setRubberBand(w.y())
                    break
        # case 2: greater than source widget
        elif pos.y() > src.y() + src.size().height():
            for n in range(src_i + 1, self.count()):
                w = self.widget(n)
                if pos.y() < w.y():
                    self.setRubberBand(w.y())
                    break
        else:
            self.setRubberBand(-1)
        e.accept()

    def dropEvent(self, e):
        self.setRubberBand(-1)
        pos = e.pos()
        src = e.source()
        src_i = self.indexOf(src)
        for n in range(self.count()):
            w = self.widget(n)
            if pos.y() < w.y() + w.size().height():
                self.dropped.emit(src_i, n)
                break
        e.accept()


# Scroll area with auto-scroll on vertical drag
class VDragScrollArea(QtWidgets.QScrollArea):
    def __init__(self, parent):
        QtWidgets.QScrollArea.__init__(self, parent)
        self.installEventFilter(self)
        self._margin = 40
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._on_auto_scroll)
        self._direction = 0
        self._speed = 10

    def setAutoScrollMargin(self, margin):
        self._margin = margin

    def setAutoScrollSpeed(self, speed):
        self._speed = speed

    def eventFilter(self, obj, e):
        if e.type() == QtCore.QEvent.DragMove:
            val = self.verticalScrollBar().value()
            height = self.viewport().height()
            y = e.pos().y()
            self._direction = 0
            if y < val + self._margin:
                self._direction = -1
            elif y > height + val - self._margin:
                self._direction = 1
            if not self._timer.isActive():
                self._timer.start()
        elif e.type() in (QtCore.QEvent.Drop, QtCore.QEvent.DragLeave):
            self._timer.stop()
        return False

    def _on_auto_scroll(self):
        val = self.verticalScrollBar().value()
        min_ = self.verticalScrollBar().minimum()
        max_ = self.verticalScrollBar().maximum()
        dy = self._direction * self._speed
        new_val = min(max_, max(min_, val + dy))
        self.verticalScrollBar().setValue(new_val)


# Widget with FlowLayout and drag and drop support between widgets
class DragDropFlowLayoutWidget(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.layout = FlowLayout()
        self.setLayout(self.layout)
        self.setAcceptDrops(True)

    def _get_index(self, pos):
        for i in range(self.layout.count()):
            if self.itemAt(i).geometry().contains(pos):
                return i
        return -1

    def mousePressEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton \
           and event.modifiers() == QtCore.Qt.ShiftModifier:
            index = self._get_index(event.pos())
            if index == -1:
                return
            drag = QtGui.QDrag(self)
            mime = QtCore.QMimeData()
            mime.setData("index", str(index).encode())
            drag.setMimeData(mime)
            pixmapi = QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_FileIcon)
            drag.setPixmap(pixmapi.pixmap(32))
            drag.exec_(QtCore.Qt.MoveAction)
        event.accept()

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        index = self._get_index(event.pos())
        source_layout = event.source()
        source_index = int(bytes(event.mimeData().data("index")).decode())
        if source_layout == self:
            if index == source_index:
                return
            widget = self.layout.itemAt(source_index).widget()
            self.layout.removeWidget(widget)
            self.layout.addWidget(widget)
            self.layout.itemList.insert(index, self.layout.itemList.pop())
        else:
            widget = source_layout.layout.itemAt(source_index).widget()
            source_layout.layout.removeWidget(widget)
            self.layout.addWidget(widget)
            if index != -1:
                self.layout.itemList.insert(index, self.layout.itemList.pop())
        event.accept()

    def addWidget(self, widget):
        self.layout.addWidget(widget)

    def count(self):
        return self.layout.count()

    def itemAt(self, i):
        return self.layout.itemAt(i)
