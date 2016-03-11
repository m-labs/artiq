import logging

from PyQt5 import QtGui, QtCore, QtWidgets
from numpy import linspace

from .ticker import Ticker


logger = logging.getLogger(__name__)


class ScanAxis(QtWidgets.QWidget):
    sigZoom = QtCore.pyqtSignal(float, int)
    sigPoints = QtCore.pyqtSignal(int)

    def __init__(self, zoomFactor):
        QtWidgets.QWidget.__init__(self)
        self.proxy = None
        self.sizePolicy().setControlType(QtWidgets.QSizePolicy.ButtonBox)
        self.ticker = Ticker()
        self.zoomFactor = zoomFactor

    def paintEvent(self, ev):
        painter = QtGui.QPainter(self)
        font = painter.font()
        avgCharWidth = QtGui.QFontMetrics(font).averageCharWidth()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # The center of the slider handles should reflect what's displayed
        # on the spinboxes.
        painter.translate(self.proxy.slider.handleWidth()/2, self.height() - 5)
        painter.drawLine(0, 0, self.width(), 0)
        realLeft = self.proxy.pixelToReal(0)
        realRight = self.proxy.pixelToReal(self.width())
        ticks, prefix, labels = self.ticker(realLeft, realRight)
        painter.drawText(0, -25, prefix)

        pen = QtGui.QPen()
        pen.setWidth(2)
        painter.setPen(pen)

        for t, l in zip(ticks, labels):
            t = self.proxy.realToPixel(t)
            painter.drawLine(t, 0, t, -5)
            painter.drawText(t - len(l)/2*avgCharWidth, -10, l)

        sliderStartPixel = self.proxy.realToPixel(self.proxy.realStart)
        sliderStopPixel = self.proxy.realToPixel(self.proxy.realStop)
        pixels = linspace(sliderStartPixel, sliderStopPixel,
                          self.proxy.numPoints)
        for p in pixels:
            p_int = int(p)
            painter.drawLine(p_int, 0, p_int, 5)
        ev.accept()

    def wheelEvent(self, ev):
        y = ev.angleDelta().y()
        if y:
            if ev.modifiers() & QtCore.Qt.ShiftModifier:
                # If shift+scroll, modify number of points.
                # TODO: This is not perfect. For high-resolution touchpads you
                # get many small events with y < 120 which should accumulate.
                # That would also match the wheel behavior of an integer
                # spinbox.
                z = int(y / 120.)
                self.sigPoints.emit(z)
            else:
                z = self.zoomFactor**(y / 120.)
                # Remove the slider-handle shift correction, b/c none of the
                # other widgets know about it. If we have the mouse directly
                # over a tick during a zoom, it should appear as if we are
                # doing zoom relative to the ticks which live in axis
                # pixel-space, not slider pixel-space.
                self.sigZoom.emit(
                    z, ev.x() - self.proxy.slider.handleWidth()/2)
            self.update()
        ev.accept()

    def eventFilter(self, obj, ev):
        if obj is not self.proxy.slider:
            return False
        if ev.type() != QtCore.QEvent.Wheel:
            return False
        self.wheelEvent(ev)
        return True


# Basic ideas from https://gist.github.com/Riateche/27e36977f7d5ea72cf4f
class ScanSlider(QtWidgets.QSlider):
    sigStartMoved = QtCore.pyqtSignal(int)
    sigStopMoved = QtCore.pyqtSignal(int)

    def __init__(self):
        QtWidgets.QSlider.__init__(self, QtCore.Qt.Horizontal)
        self.startPos = 0  # Pos and Val can differ in event handling.
        # perhaps prevPos and currPos is more accurate.
        self.stopPos = 99
        self.startVal = 0  # lower
        self.stopVal = 99  # upper
        self.offset = 0
        self.position = 0
        self.upperPressed = QtWidgets.QStyle.SC_None
        self.lowerPressed = QtWidgets.QStyle.SC_None
        self.firstMovement = False  # State var for handling slider overlap.
        self.blockTracking = False

        # We need fake sliders to keep around so that we can dynamically
        # set the stylesheets for drawing each slider later. See paintEvent.
        self.dummyStartSlider = QtWidgets.QSlider()
        self.dummyStopSlider = QtWidgets.QSlider()
        self.dummyStartSlider.setStyleSheet(
            "QSlider::handle {background:blue}")
        self.dummyStopSlider.setStyleSheet(
            "QSlider::handle {background:red}")

    # We basically superimpose two QSliders on top of each other, discarding
    # the state that remains constant between the two when drawing.
    # Everything except the handles remain constant.
    def initHandleStyleOption(self, opt, handle):
        self.initStyleOption(opt)
        if handle == "start":
            opt.sliderPosition = self.startPos
            opt.sliderValue = self.startVal
        elif handle == "stop":
            opt.sliderPosition = self.stopPos
            opt.sliderValue = self.stopVal

    # We get the range of each slider separately.
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

    def handleMousePress(self, pos, control, val, handle):
        opt = QtWidgets.QStyleOptionSlider()
        self.initHandleStyleOption(opt, handle)
        startAtEdges = (handle == "start" and
                        (self.startVal == self.minimum() or
                         self.startVal == self.maximum()))
        stopAtEdges = (handle == "stop" and
                       (self.stopVal == self.minimum() or
                        self.stopVal == self.maximum()))

        # If chosen slider at edge, treat it as non-interactive.
        if startAtEdges or stopAtEdges:
            return QtWidgets.QStyle.SC_None

        oldControl = control
        control = self.style().hitTestComplexControl(
            QtWidgets.QStyle.CC_Slider, opt, pos, self)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderHandle,
                                         self)
        if control == QtWidgets.QStyle.SC_SliderHandle:
            # no pick()- slider orientation static
            self.offset = pos.x() - sr.topLeft().x()
            self.setSliderDown(True)
            # emit

        # Needed?
        if control != oldControl:
            self.update(sr)
        return control

    def drawHandle(self, painter, handle):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        self.initHandleStyleOption(opt, handle)
        opt.subControls = QtWidgets.QStyle.SC_SliderHandle
        painter.drawComplexControl(QtWidgets.QStyle.CC_Slider, opt)

    # def triggerAction(self, action, slider):
    #     if action == QtWidgets.QAbstractSlider.SliderSingleStepAdd:
    #         if

    def setSpan(self, low, high):
        # TODO: Is this necessary? QStyle::sliderPositionFromValue appears
        # to clamp already.
        low = min(max(self.minimum(), low), self.maximum())
        high = min(max(self.minimum(), high), self.maximum())

        if low != self.startVal or high != self.stopVal:
            if low != self.startVal:
                self.startVal = low
                self.startPos = low
            if high != self.stopVal:
                self.stopVal = high
                self.stopPos = high
            self.update()

    def setStartPosition(self, val):
        if val != self.startPos:
            self.startPos = val
            if not self.hasTracking():
                self.update()
            if self.isSliderDown():
                self.sigStartMoved.emit(self.startPos)
            if self.hasTracking() and not self.blockTracking:
                self.setSpan(self.startPos, self.stopVal)

    def setStopPosition(self, val):
        if val != self.stopPos:
            self.stopPos = val
            if not self.hasTracking():
                self.update()
            if self.isSliderDown():
                self.sigStopMoved.emit(self.stopPos)
            if self.hasTracking() and not self.blockTracking:
                self.setSpan(self.startVal, self.stopPos)

    def mousePressEvent(self, ev):
        if self.minimum() == self.maximum() or (ev.buttons() ^ ev.button()):
            ev.ignore()
            return

        # Prefer stopVal in the default case.
        self.upperPressed = self.handleMousePress(
            ev.pos(), self.upperPressed, self.stopVal, "stop")
        if self.upperPressed != QtWidgets.QStyle.SC_SliderHandle:
            self.lowerPressed = self.handleMousePress(
                ev.pos(), self.upperPressed, self.startVal, "start")

        # State that is needed to handle the case where two sliders are equal.
        self.firstMovement = True
        ev.accept()

    def mouseMoveEvent(self, ev):
        if (self.lowerPressed != QtWidgets.QStyle.SC_SliderHandle and
                self.upperPressed != QtWidgets.QStyle.SC_SliderHandle):
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

        if self.firstMovement:
            if self.startPos == self.stopPos:
                # StopSlider is preferred, except in the case where
                # start == max possible value the slider can take.
                if self.startPos == self.maximum():
                    self.lowerPressed = QtWidgets.QStyle.SC_SliderHandle
                    self.upperPressed = QtWidgets.QStyle.SC_None
                self.firstMovement = False

        if self.lowerPressed == QtWidgets.QStyle.SC_SliderHandle:
            self.setStartPosition(newPos)

        if self.upperPressed == QtWidgets.QStyle.SC_SliderHandle:
            self.setStopPosition(newPos)

        ev.accept()

    def mouseReleaseEvent(self, ev):
        QtWidgets.QSlider.mouseReleaseEvent(self, ev)
        self.setSliderDown(False)  # AbstractSlider needs this
        self.lowerPressed = QtWidgets.QStyle.SC_None
        self.upperPressed = QtWidgets.QStyle.SC_None

    def paintEvent(self, ev):
        # Use QStylePainters to make redrawing as painless as possible.
        # Paint on the custom widget, using the attributes of the fake
        # slider references we keep around. setStyleSheet within paintEvent
        # leads to heavy performance penalties (and recursion?).
        # QPalettes would be nicer to use, since palette entries can be set
        # individually for each slider handle, but Windows 7 does not
        # use them. This seems to be the only way to override the colors
        # regardless of platform.
        startPainter = QtWidgets.QStylePainter(self, self.dummyStartSlider)
        stopPainter = QtWidgets.QStylePainter(self, self.dummyStopSlider)

        # Handles
        # Qt will snap sliders to 0 or maximum() if given a desired pixel
        # location outside the mapped range. So we manually just don't draw
        # the handles if they are at 0 or max.
        if self.startVal > 0 and self.startVal < self.maximum():
            self.drawHandle(startPainter, "start")
        if self.stopVal > 0 and self.stopVal < self.maximum():
            self.drawHandle(stopPainter, "stop")


# real (Sliders) => pixel (one pixel movement of sliders would increment by X)
# => range (minimum granularity that sliders understand).
class ScanProxy(QtCore.QObject):
    sigStartMoved = QtCore.pyqtSignal(float)
    sigStopMoved = QtCore.pyqtSignal(float)
    sigNumPoints = QtCore.pyqtSignal(int)

    def __init__(self, slider, axis, zoomMargin, dynamicRange):
        QtCore.QObject.__init__(self)
        self.axis = axis
        self.slider = slider
        self.realStart = 0
        self.realStop = 0
        self.numPoints = 10
        self.zoomMargin = zoomMargin
        self.dynamicRange = dynamicRange

        # Transform that maps the spinboxes to a pixel position on the
        # axis. 0 to axis.width() exclusive indicate positions which will be
        # displayed on the axis.
        # Because the axis's width will change when placed within a layout,
        # the realToPixelTransform will initially be invalid. It will be set
        # properly during the first resizeEvent, with the below transform.
        self.realToPixelTransform = -self.axis.width()/2, 1.
        self.invalidOldSizeExpected = True

    # pixel vals for sliders: 0 to slider_width - 1
    def realToPixel(self, val):
        a, b = self.realToPixelTransform
        rawVal = b*(val - a)
        # Clamp pixel values to 32 bits, b/c Qt will otherwise wrap values.
        rawVal = min(max(-(1 << 31), rawVal), (1 << 31) - 1)
        return rawVal

    # Get a point from pixel units to what the sliders display.
    def pixelToReal(self, val):
        a, b = self.realToPixelTransform
        return val/b + a

    def rangeToReal(self, val):
        pixelVal = self.slider.rangeValueToPixelPos(val)
        return self.pixelToReal(pixelVal)

    def realToRange(self, val):
        pixelVal = self.realToPixel(val)
        return self.slider.pixelPosToRangeValue(pixelVal)

    def moveStop(self, val):
        sliderX = self.realToRange(val)
        self.slider.setStopPosition(sliderX)
        self.realStop = val
        self.axis.update()  # Number of points ticks changed positions.

    def moveStart(self, val):
        sliderX = self.realToRange(val)
        self.slider.setStartPosition(sliderX)
        self.realStart = val
        self.axis.update()

    def handleStopMoved(self, rangeVal):
        self.sigStopMoved.emit(self.rangeToReal(rangeVal))

    def handleStartMoved(self, rangeVal):
        self.sigStartMoved.emit(self.rangeToReal(rangeVal))

    def handleNumPoints(self, inc):
        self.sigNumPoints.emit(self.numPoints + inc)

    def setNumPoints(self, val):
        self.numPoints = val
        self.axis.update()

    def handleZoom(self, zoomFactor, mouseXPos):
        newScale = self.realToPixelTransform[1] * zoomFactor
        refReal = self.pixelToReal(mouseXPos)
        newLeft = refReal - mouseXPos/newScale
        newZero = newLeft*newScale + self.slider.effectiveWidth()/2
        if zoomFactor > 1 and abs(newZero) > self.dynamicRange:
            return
        self.realToPixelTransform = newLeft, newScale
        self.moveStop(self.realStop)
        self.moveStart(self.realStart)

    def viewRange(self):
        newScale = self.slider.effectiveWidth()/abs(
            self.realStop - self.realStart)
        newScale *= 1 - 2*self.zoomMargin
        newCenter = (self.realStop + self.realStart)/2
        if newCenter:
            newScale = min(newScale, self.dynamicRange/abs(newCenter))
        newLeft = newCenter - self.slider.effectiveWidth()/2/newScale
        self.realToPixelTransform = newLeft, newScale
        self.moveStop(self.realStop)
        self.moveStart(self.realStart)
        self.axis.update()  # Axis normally takes care to update itself during
        # zoom. In this code path however, the zoom didn't arrive via the axis
        # widget, so we need to notify manually.

    # This function is called if the axis width, slider width, and slider
    # positions are in an inconsistent state, to initialize the widget.
    # This function handles handles the slider positions. Slider and axis
    # handle its own width changes; proxy watches for axis width resizeEvent to
    # alter mapping from real to pixel space.
    def viewRangeInit(self):
        currRangeReal = abs(self.realStop - self.realStart)
        if currRangeReal == 0:
            self.moveStop(self.realStop)
            self.moveStart(self.realStart)
            # Ill-formed snap range- move the sliders anyway,
            # because we arrived here during widget
            # initialization, where the slider positions are likely invalid.
            # This will force the sliders to have positions on the axis
            # which reflect the start/stop values currently set.
        else:
            self.viewRange()
        # Notify spinboxes manually, since slider wasn't clicked and will
        # therefore not emit signals.
        self.sigStopMoved.emit(self.realStop)
        self.sigStartMoved.emit(self.realStart)

    def snapRange(self):
        lowRange = self.zoomMargin
        highRange = 1 - self.zoomMargin
        newStart = self.pixelToReal(lowRange * self.slider.effectiveWidth())
        newStop = self.pixelToReal(highRange * self.slider.effectiveWidth())
        sliderRange = self.slider.maximum() - self.slider.minimum()
        # Signals won't fire unless slider was actually grabbed, so
        # manually update so the spinboxes know that knew values were set.
        # self.realStop/Start and the sliders themselves will be updated as a
        # consequence of ValueChanged signal in spinboxes. The slider widget
        # has guards against recursive signals in setSpan().
        if sliderRange > 0:
            self.sigStopMoved.emit(newStop)
            self.sigStartMoved.emit(newStart)

    def eventFilter(self, obj, ev):
        if obj != self.axis:
            return False
        if ev.type() != QtCore.QEvent.Resize:
            return False
        if ev.oldSize().isValid():
            oldLeft = self.pixelToReal(0)
            refWidth = ev.oldSize().width() - self.slider.handleWidth()
            refRight = self.pixelToReal(refWidth)
            newWidth = ev.size().width() - self.slider.handleWidth()
            # assert refRight > oldLeft
            newScale = newWidth/(refRight - oldLeft)
            self.realToPixelTransform = oldLeft, newScale
        else:
            # TODO: self.axis.width() is invalid during object
            # construction. The width will change when placed in a
            # layout WITHOUT a resizeEvent. Why?
            oldLeft = -ev.size().width()/2
            newScale = 1.0
            self.realToPixelTransform = oldLeft, newScale
            # We need to reinitialize the pixel transform b/c the old width
            # of the axis is no longer valid. When we have a valid transform,
            # we can then viewRange based on the desired real values.
            # The slider handle values are invalid before this point as well;
            # we set them to the correct value here, regardless of whether
            # the slider has already resized itsef or not.
            self.viewRangeInit()
            self.invalidOldSizeExpected = False
        # assert self.pixelToReal(0) == oldLeft, \
        # "{}, {}".format(self.pixelToReal(0), oldLeft)
        # Slider will update independently, making sure that the old
        # slider positions are preserved. Because of this, we can be
        # confident that the new slider position will still map to the
        # same positions in the new axis-space.
        return False


class ScanWidget(QtWidgets.QWidget):
    sigStartMoved = QtCore.pyqtSignal(float)
    sigStopMoved = QtCore.pyqtSignal(float)
    sigNumChanged = QtCore.pyqtSignal(int)

    def __init__(self, zoomFactor=1.05, zoomMargin=.1, dynamicRange=1e8):
        QtWidgets.QWidget.__init__(self)
        self.slider = slider = ScanSlider()
        self.axis = axis = ScanAxis(zoomFactor)
        self.proxy = ScanProxy(slider, axis, zoomMargin, dynamicRange)
        axis.proxy = self.proxy
        slider.setMaximum(1023)

        # Layout.
        layout = QtWidgets.QGridLayout()
        # Default size will cause axis to disappear otherwise.
        layout.setRowMinimumHeight(0, 40)
        layout.addWidget(axis, 0, 0, 1, -1)
        layout.addWidget(slider, 1, 0, 1, -1)
        self.setLayout(layout)

        # Connect signals (minus context menu)
        slider.sigStopMoved.connect(self.proxy.handleStopMoved)
        slider.sigStartMoved.connect(self.proxy.handleStartMoved)
        self.proxy.sigStopMoved.connect(self.sigStopMoved)
        self.proxy.sigStartMoved.connect(self.sigStartMoved)
        self.proxy.sigNumPoints.connect(self.sigNumChanged)
        axis.sigZoom.connect(self.proxy.handleZoom)
        axis.sigPoints.connect(self.proxy.handleNumPoints)

        # Connect event observers.
        axis.installEventFilter(self.proxy)
        slider.installEventFilter(axis)

        # Context menu entries
        self.viewRangeAct = QtWidgets.QAction("&View Range", self)
        self.snapRangeAct = QtWidgets.QAction("&Snap Range", self)
        self.viewRangeAct.triggered.connect(self.viewRange)
        self.snapRangeAct.triggered.connect(self.snapRange)

    # Spinbox and button slots. Any time the spinboxes change, ScanWidget
    # mirrors it and passes the information to the proxy.
    def setStop(self, val):
        self.proxy.moveStop(val)

    def setStart(self, val):
        self.proxy.moveStart(val)

    def setNumPoints(self, val):
        self.proxy.setNumPoints(val)

    def viewRange(self):
        self.proxy.viewRange()

    def snapRange(self):
        self.proxy.snapRange()

    def contextMenuEvent(self, ev):
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.viewRangeAct)
        menu.addAction(self.snapRangeAct)
        menu.exec(ev.globalPos())
