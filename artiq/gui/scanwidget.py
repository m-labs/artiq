import logging

from PyQt5 import QtGui, QtCore, QtWidgets
import numpy as np

from .ticker import Ticker


logger = logging.getLogger(__name__)


class ScanWidget(QtWidgets.QWidget):
    startChanged = QtCore.pyqtSignal(float)
    stopChanged = QtCore.pyqtSignal(float)
    numChanged = QtCore.pyqtSignal(int)

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.zoomMargin = .1
        self.zoomFactor = 1.05
        self.dynamicRange = 1e9
        self.suffix = ""

        self.ticker = Ticker()

        self.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        action = QtWidgets.QAction("V&iew range", self)
        action.setShortcut(QtGui.QKeySequence("CTRL+i"))
        action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        action.triggered.connect(self.viewRange)
        self.addAction(action)
        action = QtWidgets.QAction("Sna&p range", self)
        action.setShortcut(QtGui.QKeySequence("CTRL+p"))
        action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        action.triggered.connect(self.snapRange)
        self.addAction(action)

        qfm = QtGui.QFontMetrics(self.font())
        self._labelSize = QtCore.QSize(
            (self.ticker.precision + 5)*qfm.averageCharWidth(),
            qfm.lineSpacing())

        self._start, self._stop, self._num = None, None, None
        self._min, self._max = float("-inf"), float("inf")
        self._axisView = None
        self._offset, self._drag, self._rubber = None, None, None

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return QtCore.QSize(2.5*3*self._labelSize.width(),
                            4*self._labelSize.height())

    def _axisToPixel(self, val):
        a, b = self._axisView
        return a + val*b

    def _pixelToAxis(self, val):
        a, b = self._axisView
        return (val - a)/b

    def _setView(self, left, scale):
        self._axisView = left, scale
        self.update()

    def _setViewAxis(self, center, scale):
        if center:
            scale = min(scale, self.dynamicRange/abs(center))
        left = self.width()/2 - center*scale
        self._setView(left, scale)

    def _clamp(self, v):
        if v is None:
            return None
        v = max(self._min, v)
        v = min(self._max, v)
        return v

    def setStart(self, val):
        val = self._clamp(val)
        if self._start == val:
            return
        self._start = val
        self.update()
        self.startChanged.emit(val)

    def setStop(self, val):
        val = self._clamp(val)
        if self._stop == val:
            return
        self._stop = val
        self.update()
        self.stopChanged.emit(val)

    def setNum(self, val):
        if self._num == val:
            return
        self._num = val
        self.update()
        self.numChanged.emit(val)

    def setMinimum(self, v):
        self._min = v
        self.setStart(self._start)
        self.setStop(self._stop)

    def setMaximum(self, v):
        self._max = v
        self.setStart(self._start)
        self.setStop(self._stop)

    def setDecimals(self, n):
        # TODO
        # the axis should always use the most compact notation
        # do not:
        # self.ticker.precision = n
        pass

    def setSingleStep(self, v):
        # TODO
        # use this (and/or maybe decimals) to snap to "nice" values when
        # dragging
        pass

    def setSuffix(self, v):
        self.suffix = v

    def viewRange(self):
        center = (self._stop + self._start)/2
        scale = self.width()*(1 - 2*self.zoomMargin)
        if self._stop != self._start:
            scale /= abs(self._stop - self._start)
        else:
            scale = self.dynamicRange
        self._setViewAxis(center, scale)

    def snapRange(self):
        self.setStart(self._pixelToAxis(self.zoomMargin*self.width()))
        self.setStop(self._pixelToAxis((1 - self.zoomMargin)*self.width()))

    def mousePressEvent(self, ev):
        if ev.buttons() ^ ev.button():  # buttons changed
            ev.ignore()
            return
        if ev.modifiers() & QtCore.Qt.ShiftModifier:
            self._drag = "select"
            self.setStart(self._pixelToAxis(ev.x()))
            self.setStop(self._start)
        elif ev.modifiers() & QtCore.Qt.ControlModifier:
            self._drag = "zoom"
            self._offset = QtCore.QPoint(ev.x(), 0)
            self._rubber = QtWidgets.QRubberBand(
                QtWidgets.QRubberBand.Rectangle, self)
            self._rubber.setGeometry(QtCore.QRect(
                self._offset, QtCore.QPoint(ev.x(), self.height() - 1)))
            self._rubber.show()
        else:
            qfm = QtGui.QFontMetrics(self.font())
            if ev.y() <= 2.5*qfm.lineSpacing():
                self._drag = "axis"
                self._offset = ev.x() - self._axisView[0]
            # testing should match inverse drawing order for start/stop
            elif abs(self._axisToPixel(self._stop) -
                     ev.x()) < qfm.lineSpacing()/2:
                self._drag = "stop"
                self._offset = ev.x() - self._axisToPixel(self._stop)
            elif abs(self._axisToPixel(self._start) -
                     ev.x()) < qfm.lineSpacing()/2:
                self._drag = "start"
                self._offset = ev.x() - self._axisToPixel(self._start)
            else:
                self._drag = "both"
                self._offset = (ev.x() - self._axisToPixel(self._start),
                                ev.x() - self._axisToPixel(self._stop))

    def mouseMoveEvent(self, ev):
        if not self._drag:
            ev.ignore()
            return
        if self._drag == "select":
            self.setStop(self._pixelToAxis(ev.x()))
        elif self._drag == "zoom":
            self._rubber.setGeometry(QtCore.QRect(
                self._offset, QtCore.QPoint(ev.x(), self.height() - 1)
            ).normalized())
        elif self._drag == "axis":
            self._setView(ev.x() - self._offset, self._axisView[1])
        elif self._drag == "start":
            self.setStart(self._pixelToAxis(ev.x() - self._offset))
        elif self._drag == "stop":
            self.setStop(self._pixelToAxis(ev.x() - self._offset))
        elif self._drag == "both":
            self.setStart(self._pixelToAxis(ev.x() - self._offset[0]))
            self.setStop(self._pixelToAxis(ev.x() - self._offset[1]))

    def mouseReleaseEvent(self, ev):
        if self._drag == "zoom":
            self._rubber.hide()
            if self._rubber.geometry().width():
                scale = self._axisView[1]
                scale *= self.width()/self._rubber.geometry().width()
                center = self._pixelToAxis(
                    self._rubber.geometry().center().x())
                self._setViewAxis(center, scale)
        self._drag = None

    def _zoom(self, z, x):
        a, b = self._axisView
        scale = z*b
        left = x + z*(a - x)
        if z > 1 and abs(left - self.width()/2) > self.dynamicRange:
            return
        self._setView(left, scale)

    def wheelEvent(self, ev):
        y = ev.angleDelta().y()/120.
        if not y:
            return
        if ev.modifiers() & QtCore.Qt.ShiftModifier:
            self.setNum(max(1, self._num + y))
        else:
            self._zoom(self.zoomFactor**y, ev.x())

    def resizeEvent(self, ev):
        if not ev.oldSize().isValid() or not ev.oldSize().width():
            self.viewRange()
            return
        self.ticker.min_ticks = max(
            3, int(ev.size().width()/(2.5*self._labelSize.width())))
        scale = self._axisView[1]
        scale *= ev.size().width()/ev.oldSize().width()
        center = self._pixelToAxis(ev.oldSize().width()/2)
        self._setViewAxis(center, scale)

    def paintEvent(self, ev):
        painter = QtGui.QPainter(self)
        qfm = QtGui.QFontMetrics(painter.font())
        avgCharWidth = qfm.averageCharWidth()
        lineSpacing = qfm.lineSpacing()
        descent = qfm.descent()
        ascent = qfm.ascent()
        painter.translate(0, ascent)

        ticks, prefix, labels = self.ticker(self._pixelToAxis(0),
                                            self._pixelToAxis(self.width()))
        rect = QtCore.QRect(0, 0, self.width(), lineSpacing)
        painter.drawText(rect, QtCore.Qt.AlignLeft, prefix)
        painter.drawText(rect, QtCore.Qt.AlignRight, self.suffix)

        painter.translate(0, lineSpacing + ascent)

        for t, l in zip(ticks, labels):
            t = self._axisToPixel(t)
            painter.drawText(t - len(l)/2*avgCharWidth, 0, l)
            painter.drawLine(t, descent, t, lineSpacing/2)
        painter.translate(0, lineSpacing/2)

        painter.drawLine(0, 0, self.width(), 0)

        for p in np.linspace(self._axisToPixel(self._start),
                             self._axisToPixel(self._stop),
                             self._num):
            painter.drawLine(p, 0, p, lineSpacing/2)
        painter.translate(0, lineSpacing/2)

        for x, c in (self._start, QtCore.Qt.blue), (self._stop, QtCore.Qt.red):
            x = self._axisToPixel(x)
            painter.setPen(c)
            painter.setBrush(c)
            painter.drawPolygon(*(QtCore.QPointF(*i) for i in [
                (x, 0), (x - lineSpacing/2, lineSpacing),
                (x + lineSpacing/2, lineSpacing)]))
