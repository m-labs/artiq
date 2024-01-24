from PyQt5 import QtCore, QtWidgets


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
