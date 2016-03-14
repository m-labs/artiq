import logging

from PyQt5 import QtGui, QtCore, QtWidgets
from numpy import linspace

from .ticker import Ticker


logger = logging.getLogger(__name__)


class ScanAxis(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.proxy = None
        self.sizePolicy().setControlType(QtWidgets.QSizePolicy.ButtonBox)
        self.ticker = Ticker()
        qfm = QtGui.QFontMetrics(QtGui.QFont())
        lineSpacing = qfm.lineSpacing()
        descent = qfm.descent()
        self.setMinimumHeight(2*lineSpacing + descent + 5 + 5)

    def paintEvent(self, ev):
        painter = QtGui.QPainter(self)
        qfm = QtGui.QFontMetrics(painter.font())
        avgCharWidth = qfm.averageCharWidth()
        lineSpacing = qfm.lineSpacing()
        descent = qfm.descent()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # The center of the slider handles should reflect what's displayed
        # on the spinboxes.
        painter.translate(self.proxy.slider.handleWidth()/2, self.height() - 5)
        painter.drawLine(0, 0, self.width(), 0)
        realLeft = self.proxy.pixelToReal(0)
        realRight = self.proxy.pixelToReal(self.width())
        ticks, prefix, labels = self.ticker(realLeft, realRight)
        painter.drawText(0, -5-descent-lineSpacing, prefix)

        pen = QtGui.QPen()
        pen.setWidth(2)
        painter.setPen(pen)

        for t, l in zip(ticks, labels):
            t = self.proxy.realToPixel(t)
            painter.drawLine(t, 0, t, -5)
            painter.drawText(t - len(l)/2*avgCharWidth, -5-descent, l)

        sliderStartPixel = self.proxy.realToPixel(self.proxy.realStart)
        sliderStopPixel = self.proxy.realToPixel(self.proxy.realStop)
        pixels = linspace(sliderStartPixel, sliderStopPixel,
                          self.proxy.numPoints)
        for p in pixels:
            p_int = int(p)
            painter.drawLine(p_int, 0, p_int, 5)
        ev.accept()


# Basic ideas from https://gist.github.com/Riateche/27e36977f7d5ea72cf4f
class ScanSlider(QtWidgets.QSlider):
    sigStartMoved = QtCore.pyqtSignal(int)
    sigStopMoved = QtCore.pyqtSignal(int)

    def __init__(self):
        QtWidgets.QSlider.__init__(self, QtCore.Qt.Horizontal)
        self.startVal = None
        self.stopVal = None
        self.offset = None
        self.position = None
        self.pressed = None

        self.setRange(0, (1 << 15) - 1)

        # We need fake sliders to keep around so that we can dynamically
        # set the stylesheets for drawing each slider later. See paintEvent.
        # QPalettes would be nicer to use, since palette entries can be set
        # individually for each slider handle, but Windows 7 does not
        # use them. This seems to be the only way to override the colors
        # regardless of platform.
        self.dummyStartSlider = QtWidgets.QSlider()
        self.dummyStopSlider = QtWidgets.QSlider()
        self.dummyStartSlider.setStyleSheet(
            "QSlider::handle {background:blue}")
        self.dummyStopSlider.setStyleSheet(
            "QSlider::handle {background:red}")

    def pixelPosToRangeValue(self, pos):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderGroove,
                                         self)
        rangeVal = QtWidgets.QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), pos - gr.x(),
            self.effectiveWidth(), opt.upsideDown)
        return rangeVal

    def rangeValueToPixelPos(self, val):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        pixel = QtWidgets.QStyle.sliderPositionFromValue(
            self.minimum(), self.maximum(), val, self.effectiveWidth(),
            opt.upsideDown)
        return pixel

    # When calculating conversions to/from pixel space, not all of the slider's
    # width is actually usable, because the slider handle has a nonzero width.
    # We use this function as a helper when the axis needs slider information.
    def handleWidth(self):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderHandle,
                                         self)
        return sr.width()

    def effectiveWidth(self):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderGroove,
                                         self)
        return gr.width() - self.handleWidth()

    def _getStyleOptionSlider(self, val):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        opt.sliderPosition = val
        opt.sliderValue = val
        opt.subControls = QtWidgets.QStyle.SC_SliderHandle
        return opt

    def _hitHandle(self, pos, val):
        # If chosen slider at edge, treat it as non-interactive.
        if not (self.minimum() < val < self.maximum()):
            return False
        opt = self._getStyleOptionSlider(val)
        control = self.style().hitTestComplexControl(
            QtWidgets.QStyle.CC_Slider, opt, pos, self)
        if control != QtWidgets.QStyle.SC_SliderHandle:
            return False
        sr = self.style().subControlRect(
            QtWidgets.QStyle.CC_Slider, opt,
            QtWidgets.QStyle.SC_SliderHandle, self)
        self.offset = pos.x() - sr.topLeft().x()
        self.setSliderDown(True)
        # Needed?
        self.update(sr)
        return True

    def setStartPosition(self, val):
        if val == self.startVal:
            return
        self.startVal = val
        self.update()

    def setStopPosition(self, val):
        if val == self.stopVal:
            return
        self.stopVal = val
        self.update()

    def mousePressEvent(self, ev):
        if ev.buttons() ^ ev.button():
            ev.ignore()
            return
        # Prefer stopVal in the default case.
        if self._hitHandle(ev.pos(), self.stopVal):
            self.pressed = "stop"
        elif self._hitHandle(ev.pos(), self.startVal):
            self.pressed = "start"
        else:
            self.pressed = None
        ev.accept()

    def mouseMoveEvent(self, ev):
        if not self.pressed:
            ev.ignore()
            return

        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)

        # This code seems to be needed so that returning the slider to the
        # previous position is honored if a drag distance is exceeded.
        m = self.style().pixelMetric(QtWidgets.QStyle.PM_MaximumDragDistance,
                                     opt, self)
        newPos = self.pixelPosToRangeValue(ev.pos().x() - self.offset)

        if m >= 0:
            r = self.rect().adjusted(-m, -m, m, m)
            if not r.contains(ev.pos()):
                newPos = self.position

        if self.pressed == "start":
            self.setStartPosition(newPos)
            if self.hasTracking():
                self.sigStartMoved.emit(self.startVal)
        elif self.pressed == "stop":
            self.setStopPosition(newPos)
            if self.hasTracking():
                self.sigStopMoved.emit(self.stopVal)

        ev.accept()

    def mouseReleaseEvent(self, ev):
        QtWidgets.QSlider.mouseReleaseEvent(self, ev)
        self.setSliderDown(False)  # AbstractSlider needs this
        if not self.hasTracking():
            if self.pressed == "start":
                self.sigStartMoved.emit(self.startVal)
            elif self.pressed == "stop":
                self.sigStopMoved.emit(self.stopVal)
        self.pressed = None

    def paintEvent(self, ev):
        # Use the pre-parsed, styled sliders.
        startPainter = QtWidgets.QStylePainter(self, self.dummyStartSlider)
        stopPainter = QtWidgets.QStylePainter(self, self.dummyStopSlider)
        # Only draw handles that are not railed
        if self.minimum() < self.startVal < self.maximum():
            opt = self._getStyleOptionSlider(self.startVal)
            startPainter.drawComplexControl(QtWidgets.QStyle.CC_Slider, opt)
        if self.minimum() < self.stopVal < self.maximum():
            opt = self._getStyleOptionSlider(self.stopVal)
            stopPainter.drawComplexControl(QtWidgets.QStyle.CC_Slider, opt)


# real (Sliders) => pixel (one pixel movement of sliders would increment by X)
# => range (minimum granularity that sliders understand).
class ScanWidget(QtWidgets.QWidget):
    sigStartMoved = QtCore.pyqtSignal(float)
    sigStopMoved = QtCore.pyqtSignal(float)
    sigNumChanged = QtCore.pyqtSignal(int)

    def __init__(self, zoomFactor=1.05, zoomMargin=.1, dynamicRange=1e9):
        QtWidgets.QWidget.__init__(self)
        self.slider = slider = ScanSlider()
        self.axis = axis = ScanAxis()
        axis.proxy = self

        # Layout.
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(axis)
        layout.addWidget(slider)
        self.setLayout(layout)

        # Context menu entries
        self.menu = QtWidgets.QMenu(self)
        viewRangeAct = QtWidgets.QAction("&View Range", self)
        viewRangeAct.triggered.connect(self.viewRange)
        self.menu.addAction(viewRangeAct)
        snapRangeAct = QtWidgets.QAction("&Snap Range", self)
        snapRangeAct.triggered.connect(self.snapRange)
        self.menu.addAction(snapRangeAct)

        self.realStart = None
        self.realStop = None
        self.numPoints = None
        self.zoomMargin = zoomMargin
        self.dynamicRange = dynamicRange
        self.zoomFactor = zoomFactor

        self.realToPixelTransform = -self.axis.width()/2, 1.

        # Connect event observers.
        axis.installEventFilter(self)
        slider.installEventFilter(self)
        slider.sigStopMoved.connect(self._handleStopMoved)
        slider.sigStartMoved.connect(self._handleStartMoved)

    def contextMenuEvent(self, ev):
        self.menu.popup(ev.globalPos())

    # pixel vals for sliders: 0 to slider_width - 1
    def realToPixel(self, val):
        a, b = self.realToPixelTransform
        rawVal = b*(val - a)
        # Clamp pixel values to 32 bits, b/c Qt will otherwise wrap values.
        rawVal = min(max(-(1 << 31), rawVal), (1 << 31) - 1)
        return rawVal

    def pixelToReal(self, val):
        a, b = self.realToPixelTransform
        return val/b + a

    def rangeToReal(self, val):
        pixelVal = self.slider.rangeValueToPixelPos(val)
        return self.pixelToReal(pixelVal)

    def realToRange(self, val):
        pixelVal = self.realToPixel(val)
        return self.slider.pixelPosToRangeValue(pixelVal)

    def setView(self, left, scale):
        self.realToPixelTransform = left, scale
        sliderX = self.realToRange(self.realStop)
        self.slider.setStopPosition(sliderX)
        sliderX = self.realToRange(self.realStart)
        self.slider.setStartPosition(sliderX)
        self.axis.update()

    def setStop(self, val):
        if self.realStop == val:
            return
        sliderX = self.realToRange(val)
        self.slider.setStopPosition(sliderX)
        self.realStop = val
        self.axis.update()  # Number of points ticks changed positions.
        self.sigStopMoved.emit(val)

    def setStart(self, val):
        if self.realStart == val:
            return
        sliderX = self.realToRange(val)
        self.slider.setStartPosition(sliderX)
        self.realStart = val
        self.axis.update()
        self.sigStartMoved.emit(val)

    def setNumPoints(self, val):
        if self.numPoints == val:
            return
        self.numPoints = val
        self.axis.update()
        self.sigNumChanged.emit(val)

    def viewRange(self):
        newScale = self.slider.effectiveWidth()/abs(
            self.realStop - self.realStart)
        newScale *= 1 - 2*self.zoomMargin
        newCenter = (self.realStop + self.realStart)/2
        if newCenter:
            newScale = min(newScale, self.dynamicRange/abs(newCenter))
        newLeft = newCenter - self.slider.effectiveWidth()/2/newScale
        self.setView(newLeft, newScale)

    def snapRange(self):
        lowRange = self.zoomMargin
        highRange = 1 - self.zoomMargin
        newStart = self.pixelToReal(lowRange * self.slider.effectiveWidth())
        newStop = self.pixelToReal(highRange * self.slider.effectiveWidth())
        self.setStart(newStart)
        self.setStop(newStop)

    def _handleStartMoved(self, rangeVal):
        val = self.rangeToReal(rangeVal)
        self.realStart = val
        self.axis.update()
        self.sigStartMoved.emit(val)

    def _handleStopMoved(self, rangeVal):
        val = self.rangeToReal(rangeVal)
        self.realStop = val
        self.axis.update()
        self.sigStopMoved.emit(val)

    def _handleZoom(self, zoomFactor, mouseXPos):
        newScale = self.realToPixelTransform[1] * zoomFactor
        refReal = self.pixelToReal(mouseXPos)
        newLeft = refReal - mouseXPos/newScale
        newZero = newLeft*newScale + self.slider.effectiveWidth()/2
        if zoomFactor > 1 and abs(newZero) > self.dynamicRange:
            return
        self.setView(newLeft, newScale)

    def wheelEvent(self, ev):
        y = ev.angleDelta().y()
        if ev.modifiers() & QtCore.Qt.ShiftModifier:
            # If shift+scroll, modify number of points.
            # TODO: This is not perfect. For high-resolution touchpads you
            # get many small events with y < 120 which should accumulate.
            # That would also match the wheel behavior of an integer
            # spinbox.
            z = int(y / 120.)
            if z:
                self.setNumPoints(max(1, self.numPoints + z))
            ev.accept()
        elif ev.modifiers() & QtCore.Qt.ControlModifier:
            # Remove the slider-handle shift correction, b/c none of the
            # other widgets know about it. If we have the mouse directly
            # over a tick during a zoom, it should appear as if we are
            # doing zoom relative to the ticks which live in axis
            # pixel-space, not slider pixel-space.
            if y:
                z = self.zoomFactor**(y / 120.)
                self._handleZoom(z, ev.x() - self.slider.handleWidth()/2)
            ev.accept()
        else:
            ev.ignore()

    def resizeEvent(self, ev):
        if ev.oldSize().isValid():
            oldLeft = self.pixelToReal(0)
            refWidth = ev.oldSize().width() - self.slider.handleWidth()
            refRight = self.pixelToReal(refWidth)
            newWidth = ev.size().width() - self.slider.handleWidth()
            newScale = newWidth/(refRight - oldLeft)
            center = (self.realStop + self.realStart)/2
            if center:
                newScale = min(newScale, self.dynamicRange/abs(center))
            self.setView(oldLeft, newScale)
        else:
            self.viewRange()

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Wheel:
            ev.ignore()
            return True
        if ev.type() == QtCore.QEvent.Resize:
            ev.ignore()
            return True
        return False
