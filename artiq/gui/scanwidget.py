import logging

from PyQt5 import QtGui, QtCore, QtWidgets
import numpy as np

from .ticker import Ticker


logger = logging.getLogger(__name__)


class ScanWidget(QtWidgets.QSlider):
    startChanged = QtCore.pyqtSignal(float)
    stopChanged = QtCore.pyqtSignal(float)
    numChanged = QtCore.pyqtSignal(int)

    def __init__(self, zoomFactor=1.05, zoomMargin=.1, dynamicRange=1e9):
        QtWidgets.QSlider.__init__(self, QtCore.Qt.Horizontal)
        self.zoomMargin = zoomMargin
        self.dynamicRange = dynamicRange
        self.zoomFactor = zoomFactor

        self.ticker = Ticker()

        self.menu = QtWidgets.QMenu(self)
        action = QtWidgets.QAction("&View Range", self)
        action.triggered.connect(self.viewRange)
        self.menu.addAction(action)
        action = QtWidgets.QAction("&Snap Range", self)
        action.triggered.connect(self.snapRange)
        self.menu.addAction(action)

        self._startSlider = QtWidgets.QSlider()
        self._startSlider.setStyleSheet("QSlider::handle {background:blue}")
        self._stopSlider = QtWidgets.QSlider()
        self._stopSlider.setStyleSheet("QSlider::handle {background:red}")

        self.setRange(0, 4095)

        self._start, self._stop, self._num = None, None, None
        self._axisView, self._sliderView = None, None
        self._offset, self._pressed, self._dragLeft = None, None, None

    def contextMenuEvent(self, ev):
        self.menu.popup(ev.globalPos())

    def _axisToPixel(self, val):
        a, b = self._axisView
        return a + val*b

    def _pixelToAxis(self, val):
        a, b = self._axisView
        return (val - a)/b

    def _setView(self, axis_left, axis_scale):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        g = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                        QtWidgets.QStyle.SC_SliderGroove,
                                        self)
        h = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                        QtWidgets.QStyle.SC_SliderHandle,
                                        self)
        slider_left = g.x() + h.width()/2
        slider_scale = (self.maximum() - self.minimum())/(
            g.width() - h.width())

        self._axisView = axis_left, axis_scale
        self._sliderView = ((axis_left - slider_left)*slider_scale,
                            axis_scale*slider_scale)
        self.update()

    def setStart(self, val):
        if self._start == val:
            return
        self._start = val
        self.update()
        self.startChanged.emit(val)

    def setStop(self, val):
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

    def viewRange(self):
        center = (self._stop + self._start)/2
        scale = self.width()*(1 - 2*self.zoomMargin)
        if self._stop != self._start:
            scale /= abs(self._stop - self._start)
            if center:
                scale = min(scale, self.dynamicRange/abs(center))
        else:
            scale = self.dynamicRange
            if center:
                scale /= abs(center)
        left = self.width()/2 - center*scale
        self._setView(left, scale)

    def snapRange(self):
        self.setStart(self._pixelToAxis(self.zoomMargin*self.width()))
        self.setStop(self._pixelToAxis((1 - self.zoomMargin)*self.width()))

    def _getStyleOptionSlider(self, val):
        a, b = self._sliderView
        val = a + val*b
        if not (self.minimum() <= val <= self.maximum()):
            return None
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        opt.sliderPosition = val
        opt.sliderValue = val
        opt.subControls = QtWidgets.QStyle.SC_SliderHandle
        return opt

    def _hitHandle(self, pos, val):
        opt = self._getStyleOptionSlider(val)
        if not opt:
            return False
        control = self.style().hitTestComplexControl(
            QtWidgets.QStyle.CC_Slider, opt, pos, self)
        if control != QtWidgets.QStyle.SC_SliderHandle:
            return False
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderHandle,
                                         self)
        self._offset = pos.x() - sr.center().x()
        self.setSliderDown(True)
        return True

    def mousePressEvent(self, ev):
        if ev.buttons() ^ ev.button():
            ev.ignore()
            return
        if self._hitHandle(ev.pos(), self._stop):
            self._pressed = "stop"
        elif self._hitHandle(ev.pos(), self._start):
            self._pressed = "start"
        else:
            self._pressed = "axis"
            self._offset = ev.x()
            self._dragLeft = self._axisView[0]

    def mouseMoveEvent(self, ev):
        if not self._pressed:
            ev.ignore()
            return
        if self._pressed == "stop":
            self._stop = self._pixelToAxis(ev.x() - self._offset)
            self.update()
            if self.hasTracking():
                self.stopChanged.emit(self._stop)
        elif self._pressed == "start":
            self._start = self._pixelToAxis(ev.x() - self._offset)
            self.update()
            if self.hasTracking():
                self.startChanged.emit(self._start)
        elif self._pressed == "axis":
            self._setView(self._dragLeft + ev.x() - self._offset,
                          self._axisView[1])

    def mouseReleaseEvent(self, ev):
        QtWidgets.QSlider.mouseReleaseEvent(self, ev)
        self.setSliderDown(False)
        if self._pressed == "start":
            self.startChanged.emit(self._start)
        elif self._pressed == "stop":
            self.stopChanged.emit(self._stop)
        self._pressed = None

    def _zoom(self, z, x):
        a, b = self._axisView
        scale = z*b
        left = x - z*(x - a)
        if z > 1 and abs(left - self.width()/2) > self.dynamicRange:
            return
        self._setView(left, scale)

    def wheelEvent(self, ev):
        y = ev.angleDelta().y()/120.
        if ev.modifiers() & QtCore.Qt.ShiftModifier:
            if y:
                self.setNum(max(1, self._num + y))
        elif ev.modifiers() & QtCore.Qt.ControlModifier:
            if y:
                self._zoom(self.zoomFactor**y, ev.x())
        else:
            ev.ignore()

    def resizeEvent(self, ev):
        if not ev.oldSize().isValid():
            self.viewRange()
            return
        a, b = self._axisView
        scale = b*ev.size().width()/ev.oldSize().width()
        center = (self._stop + self._start)/2
        if center:
            scale = min(scale, self.dynamicRange/abs(center))
        left = a*scale/b
        self._setView(left, scale)

    def paintEvent(self, ev):
        self._paintSliders()
        self._paintAxis()

    def _paintAxis(self):
        painter = QtGui.QPainter(self)
        qfm = QtGui.QFontMetrics(painter.font())
        avgCharWidth = qfm.averageCharWidth()
        lineSpacing = qfm.lineSpacing()
        descent = qfm.descent()
        ascent = qfm.ascent()
        height = qfm.height()
        # painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # TODO: make drawable area big enough and move axis higher
        painter.translate(0, ascent - 15)
        ticks, prefix, labels = self.ticker(self._pixelToAxis(0),
                                            self._pixelToAxis(self.width()))
        painter.drawText(0, 0, prefix)

        pen = QtGui.QPen()
        pen.setWidth(2)
        painter.setPen(pen)

        painter.translate(0, lineSpacing)
        for t, l in zip(ticks, labels):
            t = self._axisToPixel(t)
            painter.drawLine(t, descent, t, height/2)
            painter.drawText(t - len(l)/2*avgCharWidth, 0, l)
        painter.drawLine(0, height/2, self.width(), height/2)

        painter.translate(0, height)
        for p in np.linspace(self._axisToPixel(self._start),
                             self._axisToPixel(self._stop),
                             self._num):
            # TODO: is drawing far outside the viewport dangerous?
            painter.drawLine(p, 0, p, -height/2)

    def _paintSliders(self):
        startPainter = QtWidgets.QStylePainter(self, self._startSlider)
        stopPainter = QtWidgets.QStylePainter(self, self._stopSlider)
        opt = self._getStyleOptionSlider(self._start)
        if opt:
            startPainter.drawComplexControl(QtWidgets.QStyle.CC_Slider, opt)
        opt = self._getStyleOptionSlider(self._stop)
        if opt:
            stopPainter.drawComplexControl(QtWidgets.QStyle.CC_Slider, opt)
