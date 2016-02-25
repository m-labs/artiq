from PyQt5 import QtGui, QtCore, QtWidgets

from .ticker import Ticker


class ScanAxis(QtWidgets.QWidget):
    sigZoom = QtCore.pyqtSignal(float, int)

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
        realMin = self.proxy.pixelToReal(0)
        realMax = self.proxy.pixelToReal(self.width())

        ticks, prefix, labels = self.ticker(realMin, realMax)
        for t, l in zip(ticks, labels):
            t = self.proxy.realToPixel(t)
            textCenter = (len(l)/2.0)*avgCharWidth
            painter.drawLine(t, 5, t, -5)
            painter.drawText(t - textCenter, -10, l)
        painter.resetTransform()
        painter.drawText(0, 10, prefix)
        # TODO:
        # QtWidgets.QWidget.paintEvent(self, ev)?
        # ev.accept() ?

    def wheelEvent(self, ev):
        y = ev.angleDelta().y()
        if y:
            z = self.zoomFactor**(y / 120.)
            # Remove the slider-handle shift correction, b/c none of the other
            # widgets know about it. If we have the mouse directly over a tick
            # during a zoom, it should appear as if we are doing zoom relative
            # to the ticks which live in axis pixel-space, not slider
            # pixel-space.
            self.sigZoom.emit(z, ev.x() - self.proxy.slider.handleWidth()/2)
            self.update()
        ev.accept()


# Basic ideas from https://gist.github.com/Riateche/27e36977f7d5ea72cf4f
class ScanSlider(QtWidgets.QSlider):
    sigMinMoved = QtCore.pyqtSignal(int)
    sigMaxMoved = QtCore.pyqtSignal(int)
    noSlider, minSlider, maxSlider = range(3)
    maxStyle = "QSlider::handle {background:red}"
    minStyle = "QSlider::handle {background:blue}"

    def __init__(self):
        QtWidgets.QSlider.__init__(self, QtCore.Qt.Horizontal)
        self.minPos = 0  # Pos and Val can differ in event handling.
        # perhaps prevPos and currPos is more accurate.
        self.maxPos = 99
        self.minVal = 0  # lower
        self.maxVal = 99  # upper
        self.offset = 0
        self.position = 0
        self.lastPressed = ScanSlider.noSlider
        self.selectedHandle = ScanSlider.minSlider
        self.upperPressed = QtWidgets.QStyle.SC_None
        self.lowerPressed = QtWidgets.QStyle.SC_None
        self.firstMovement = False  # State var for handling slider overlap.
        self.blockTracking = False

        # We need fake sliders to keep around so that we can dynamically
        # set the stylesheets for drawing each slider later. See paintEvent.
        self.dummyMinSlider = QtWidgets.QSlider()
        self.dummyMaxSlider = QtWidgets.QSlider()
        self.dummyMinSlider.setStyleSheet(ScanSlider.minStyle)
        self.dummyMaxSlider.setStyleSheet(ScanSlider.maxStyle)

    # We basically superimpose two QSliders on top of each other, discarding
    # the state that remains constant between the two when drawing.
    # Everything except the handles remain constant.
    def initHandleStyleOption(self, opt, handle):
        self.initStyleOption(opt)
        if handle == ScanSlider.minSlider:
            opt.sliderPosition = self.minPos
            opt.sliderValue = self.minVal
        elif handle == ScanSlider.maxSlider:
            opt.sliderPosition = self.maxPos
            opt.sliderValue = self.maxVal
        else:
            pass  # AssertionErrors

    # We get the range of each slider separately.
    def pixelPosToRangeValue(self, pos):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)

        gr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderGroove,
                                         self)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderHandle,
                                         self)

        sliderLength = sr.width()
        sliderMin = gr.x()
        # For historical reasons right() returns left()+width() - 1
        # x() is equivalent to left().
        sliderMax = gr.right() - sliderLength + 1
        return QtWidgets.QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), pos - sliderMin,
            sliderMax - sliderMin, opt.upsideDown)

    def rangeValueToPixelPos(self, val):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)

        gr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderGroove,
                                         self)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderHandle,
                                         self)

        sliderLength = sr.width()
        sliderMin = gr.x()
        sliderMax = gr.right() - sliderLength + 1

        pixel = QtWidgets.QStyle.sliderPositionFromValue(
            self.minimum(), self.maximum(), val, sliderMax - sliderMin,
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
        sliderLength = self.handleWidth()
        sliderMin = gr.x()
        sliderMax = gr.right() - sliderLength + 1
        return sliderMax - sliderMin

    # If groove and axis are not aligned (and they should be), we can use
    # this function to calculate the offset between them.
    def grooveX(self):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderGroove,
                                         self)
        return gr.x()

    def handleMousePress(self, pos, control, val, handle):
        opt = QtWidgets.QStyleOptionSlider()
        self.initHandleStyleOption(opt, handle)
        oldControl = control
        control = self.style().hitTestComplexControl(
            QtWidgets.QStyle.CC_Slider, opt, pos, self)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt,
                                         QtWidgets.QStyle.SC_SliderHandle,
                                         self)
        if control == QtWidgets.QStyle.SC_SliderHandle:
            # no pick()- slider orientation static
            self.offset = pos.x() - sr.topLeft().x()
            self.lastPressed = handle
            self.setSliderDown(True)
            self.selectedHandle = handle
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

    def setLowerValue(self, val):
        self.setSpan(val, self.maxVal)

    def setUpperValue(self, val):
        self.setSpan(self.minVal, val)

    def setSpan(self, lower, upper):
        def bound(min, curr, max):
            if curr < min:
                return min
            elif curr > max:
                return max
            else:
                return curr

        low = bound(self.minimum(), lower, self.maximum())
        high = bound(self.minimum(), upper, self.maximum())

        if low != self.minVal or high != self.maxVal:
            if low != self.minVal:
                self.minVal = low
                self.minPos = low
                # emit
            if high != self.maxVal:
                self.maxVal = high
                self.maxPos = high
                # emit
            # emit spanChanged
            self.update()

    def setLowerPosition(self, val):
        if val != self.minPos:
            self.minPos = val
            if not self.hasTracking():
                self.update()
            if self.isSliderDown():
                self.sigMinMoved.emit(self.minPos)
            if self.hasTracking() and not self.blockTracking:
                self.setLowerValue(val)

    def setUpperPosition(self, val):
        if val != self.maxPos:
            self.maxPos = val
            if not self.hasTracking():
                self.update()
            if self.isSliderDown():
                self.sigMaxMoved.emit(self.maxPos)
            if self.hasTracking() and not self.blockTracking:
                self.setUpperValue(val)

    def mousePressEvent(self, ev):
        if self.minimum() == self.maximum() or (ev.buttons() ^ ev.button()):
            ev.ignore()
            return

        # Prefer maxVal in the default case.
        self.upperPressed = self.handleMousePress(
            ev.pos(), self.upperPressed, self.maxVal, ScanSlider.maxSlider)
        if self.upperPressed != QtWidgets.QStyle.SC_SliderHandle:
            self.lowerPressed = self.handleMousePress(
                ev.pos(), self.upperPressed, self.minVal, ScanSlider.minSlider)

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
            if self.minPos == self.maxPos:
                # MaxSlider is preferred, except in the case where min == max
                # possible value the slider can take.
                if self.minPos == self.maximum():
                    self.lowerPressed = QtWidgets.QStyle.SC_SliderHandle
                    self.upperPressed = QtWidgets.QStyle.SC_None
                self.firstMovement = False

        if self.lowerPressed == QtWidgets.QStyle.SC_SliderHandle:
            newPos = min(newPos, self.maxVal)
            self.setLowerPosition(newPos)

        if self.upperPressed == QtWidgets.QStyle.SC_SliderHandle:
            newPos = max(newPos, self.minVal)
            self.setUpperPosition(newPos)

        ev.accept()

    def mouseReleaseEvent(self, ev):
        QtWidgets.QSlider.mouseReleaseEvent(self, ev)
        self.setSliderDown(False)  # AbstractSlider needs this
        self.lowerPressed = QtWidgets.QStyle.SC_None
        self.upperPressed = QtWidgets.QStyle.SC_None

    def paintEvent(self, ev):
        # Use QStylePainters to make redrawing as painless as possible.
        painter = QtWidgets.QStylePainter(self)
        # Paint on the custom widget, using the attributes of the fake
        # slider references we keep around. setStyleSheet within paintEvent
        # leads to heavy performance penalties (and recursion?).
        # QPalettes would be nicer to use, since palette entries can be set
        # individually for each slider handle, but Windows 7 does not
        # use them. This seems to be the only way to override the colors
        # regardless of platform.
        minPainter = QtWidgets.QStylePainter(self, self.dummyMinSlider)
        maxPainter = QtWidgets.QStylePainter(self, self.dummyMaxSlider)

        # Groove
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        opt.sliderValue = 0
        opt.sliderPosition = 0
        opt.subControls = QtWidgets.QStyle.SC_SliderGroove
        painter.drawComplexControl(QtWidgets.QStyle.CC_Slider, opt)

        # Handles
        self.drawHandle(minPainter, ScanSlider.minSlider)
        self.drawHandle(maxPainter, ScanSlider.maxSlider)


# real (Sliders) => pixel (one pixel movement of sliders would increment by X)
# => range (minimum granularity that sliders understand).
class ScanProxy(QtCore.QObject):
    sigMinMoved = QtCore.pyqtSignal(float)
    sigMaxMoved = QtCore.pyqtSignal(float)

    def __init__(self, slider, axis, rangeFactor):
        QtCore.QObject.__init__(self)
        self.axis = axis
        self.slider = slider
        self.realMin = 0
        self.realMax = 0
        self.numPoints = 10
        self.rangeFactor = rangeFactor

        # Transform that maps the spinboxes to a pixel position on the
        # axis. 0 to axis.width() exclusive indicate positions which will be
        # displayed on the axis.
        # Because the axis's width will change when placed within a layout,
        # the realToPixelTransform will initially be invalid. It will be set
        # properly during the first resizeEvent, with the below transform.
        self.realToPixelTransform = self.calculateNewRealToPixel(
            -self.axis.width()/2, 1.0)
        self.invalidOldSizeExpected = True
        self.axis.installEventFilter(self)

    # What real value should map to the axis/slider left? This doesn't depend
    # on any public members so we can make decisions about centering during
    # resize and zoom events.
    def calculateNewRealToPixel(self, targetLeft, targetScale):
        return QtGui.QTransform.fromScale(targetScale, 1).translate(
            -targetLeft, 0)

    # pixel vals for sliders: 0 to slider_width - 1
    def realToPixel(self, val):
        return (QtCore.QPointF(val, 0) * self.realToPixelTransform).x()

    # Get a point from pixel units to what the sliders display.
    def pixelToReal(self, val):
        (revXform, invertible) = self.realToPixelTransform.inverted()
        if not invertible:
            revXform = (QtGui.QTransform.fromTranslate(
                -self.realToPixelTransform.dx(), 0) *
                        QtGui.QTransform.fromScale(
                            1/self.realToPixelTransform.m11(), 0))
        realPoint = QtCore.QPointF(val, 0) * revXform
        return realPoint.x()

    def rangeToReal(self, val):
        # gx = self.slider.grooveX()
        # ax = self.axis.x()
        # assert gx == ax, "gx: {}, ax: {}".format(gx, ax)
        pixelVal = self.slider.rangeValueToPixelPos(val)
        return self.pixelToReal(pixelVal)

    def realToRange(self, val):
        pixelVal = self.realToPixel(val)
        return self.slider.pixelPosToRangeValue(pixelVal)

    def moveMax(self, val):
        sliderX = self.realToRange(val)
        self.slider.setUpperPosition(sliderX)
        self.realMax = val

    def moveMin(self, val):
        sliderX = self.realToRange(val)
        self.slider.setLowerPosition(sliderX)
        self.realMin = val

    def handleMaxMoved(self, rangeVal):
        self.sigMaxMoved.emit(self.rangeToReal(rangeVal))

    def handleMinMoved(self, rangeVal):
        self.sigMinMoved.emit(self.rangeToReal(rangeVal))

    def handleZoom(self, zoomFactor, mouseXPos):
        newScale = self.realToPixelTransform.m11() * zoomFactor
        refReal = self.pixelToReal(mouseXPos)
        newLeft = refReal - mouseXPos/newScale
        self.realToPixelTransform = self.calculateNewRealToPixel(
            newLeft, newScale)
        self.moveMax(self.realMax)
        self.moveMin(self.realMin)

    def zoomToFit(self):
        currRangeReal = abs(self.realMax - self.realMin)
        assert self.rangeFactor > 2
        proportion = self.rangeFactor/(self.rangeFactor - 2)
        newScale = self.slider.effectiveWidth()/(proportion*currRangeReal)
        newLeft = self.realMin - self.slider.effectiveWidth() \
            / (self.rangeFactor*newScale)
        self.realToPixelTransform = self.calculateNewRealToPixel(
            newLeft, newScale)
        self.printTransform()
        self.moveMax(self.realMax)
        self.moveMin(self.realMin)
        self.axis.update()

    def fitToView(self):
        lowRange = 1.0/self.rangeFactor
        highRange = (self.rangeFactor - 1)/self.rangeFactor
        newMin = self.pixelToReal(lowRange * self.slider.effectiveWidth())
        newMax = self.pixelToReal(highRange * self.slider.effectiveWidth())
        sliderRange = self.slider.maximum() - self.slider.minimum()
        assert sliderRange > 0
        self.moveMin(newMin)
        self.moveMax(newMax)
        # Signals won't fire unless slider was actually grabbed, so
        # manually update so the spinboxes know that knew values were set.
        # self.realMax/Min will be updated as a consequence of ValueChanged
        # signal in spinboxes.
        self.sigMaxMoved.emit(newMax)
        self.sigMinMoved.emit(newMin)

    def eventFilter(self, obj, ev):
        if obj != self.axis:
            return False
        if ev.type() != QtCore.QEvent.Resize:
            return False
        oldLeft = self.pixelToReal(0)
        if ev.oldSize().isValid():
            refWidth = ev.oldSize().width() - self.slider.handleWidth()
            refRight = self.pixelToReal(refWidth)
            newWidth = ev.size().width() - self.slider.handleWidth()
            assert refRight > oldLeft
            newScale = newWidth/(refRight - oldLeft)
        else:
            # TODO: self.axis.width() is invalid during object
            # construction. The width will change when placed in a
            # layout WITHOUT a resizeEvent. Why?
            oldLeft = -ev.size().width()/2
            newScale = 1.0
            self.invalidOldSizeExpected = False
        self.realToPixelTransform = self.calculateNewRealToPixel(
            oldLeft, newScale)
        # assert self.pixelToReal(0) == oldLeft, \
        # "{}, {}".format(self.pixelToReal(0), oldLeft)
        # Slider will update independently, making sure that the old
        # slider positions are preserved. Because of this, we can be
        # confident that the new slider position will still map to the
        # same positions in the new axis-space.
        return False

    def printTransform(self):
        print("m11: {}, dx: {}".format(
            self.realToPixelTransform.m11(), self.realToPixelTransform.dx()))
        (inverted, invertible) = self.realToPixelTransform.inverted()
        print("m11: {}, dx: {}, singular: {}".format(
            inverted.m11(), inverted.dx(), not invertible))


class ScanWidget(QtWidgets.QWidget):
    sigMinMoved = QtCore.pyqtSignal(float)
    sigMaxMoved = QtCore.pyqtSignal(float)

    def __init__(self, zoomFactor=1.05, rangeFactor=6):
        QtWidgets.QWidget.__init__(self)
        slider = ScanSlider()
        axis = ScanAxis(zoomFactor)
        zoomFitButton = QtWidgets.QPushButton("View Range")
        fitViewButton = QtWidgets.QPushButton("Snap Range")
        self.proxy = ScanProxy(slider, axis, rangeFactor)
        axis.proxy = self.proxy

        # Layout.
        layout = QtWidgets.QGridLayout()
        # Default size will cause axis to disappear otherwise.
        layout.setRowMinimumHeight(0, 40)
        layout.addWidget(axis, 0, 0, 1, -1)
        layout.addWidget(slider, 1, 0, 1, -1)
        layout.addWidget(zoomFitButton, 2, 0)
        layout.addWidget(fitViewButton, 2, 1)
        self.setLayout(layout)

        # Connect signals
        slider.sigMaxMoved.connect(self.proxy.handleMaxMoved)
        slider.sigMinMoved.connect(self.proxy.handleMinMoved)
        self.proxy.sigMaxMoved.connect(self.sigMaxMoved)
        self.proxy.sigMinMoved.connect(self.sigMinMoved)
        axis.sigZoom.connect(self.proxy.handleZoom)
        fitViewButton.clicked.connect(self.fitToView)
        zoomFitButton.clicked.connect(self.zoomToFit)

        # Connect event observers.

    # Spinbox and button slots. Any time the spinboxes change, ScanWidget
    # mirrors it and passes the information to the proxy.
    def setMax(self, val):
        self.proxy.moveMax(val)

    def setMin(self, val):
        self.proxy.moveMin(val)

    def setNumPoints(self, val):
        pass

    def zoomToFit(self):
        self.proxy.zoomToFit()

    def fitToView(self):
        self.proxy.fitToView()

    def reset(self):
        self.proxy.reset()
