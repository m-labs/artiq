import re
from math import inf, copysign
from PyQt5 import QtCore, QtGui, QtWidgets


_float_acceptable = re.compile(
    r"([-+]?\d*(?:\d|\.\d|\d\.)\d*)(?:[eE]([-+]?\d+))?",
)
_float_intermediate = re.compile(
    r"[-+]?\d*\.?\d*(?:(?:(?<=\d)|(?<=\d\.))[eE][-+]?\d*)?",
)
_exp_shorten = re.compile(r"e\+?0*")


class ScientificSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setGroupSeparatorShown(False)
        self.setInputMethodHints(QtCore.Qt.ImhNone)
        self.setCorrectionMode(self.CorrectToPreviousValue)
        # singleStep: resolution for step, buttons, accelerators
        # decimals: absolute rounding granularity
        # precision: number of significant digits shown, %g precision
        self.setPrecision()
        self.setRelativeStep()
        self.setRange(-inf, inf)
        self.setValue(0)
        # self.setKeyboardTracking(False)

    def setPrecision(self, d=None):
        if d is None:
            d = self.decimals() + 3
        self._precision = max(1, int(d))
        self._fmt = "{{:.{}g}}".format(self._precision)

    def precision(self):
        return self._precision

    def setRelativeStep(self, s=None):
        if s is None:
            s = 1 + self.singleStep()
        self._relative_step = max(1 + 10**-self.decimals(), float(s))

    def relativeStep(self):
        return self._relative_step

    def setGroupSeparatorShown(self, s):
        if s:
            raise NotImplementedError

    def textFromValue(self, v):
        t = self._fmt.format(v)
        t = re.sub(_exp_shorten, "e", t, 1)
        return t

    def valueFromText(self, text):
        clean = text
        if self.prefix():
            clean = clean.split(self.prefix(), 1)[-1]
        if self.suffix():
            clean = clean.rsplit(self.suffix(), 1)[0]
        return round(float(clean), self.decimals())

    def validate(self, text, pos):
        clean = text
        if self.prefix():
            clean = clean.split(self.prefix(), 1)[-1]
        if self.suffix():
            clean = clean.rsplit(self.suffix(), 1)[0]
        try:
            float(clean)  # faster than matching
            return QtGui.QValidator.Acceptable, text, pos
        except ValueError:
            if re.fullmatch(_float_intermediate, clean):
                return QtGui.QValidator.Intermediate, text, pos
            return QtGui.QValidator.Invalid, text, pos

    def stepBy(self, s):
        if abs(s) < 10:  # unaccelerated buttons, keys, wheel/trackpad
            super().stepBy(s)
        else:  # accelerated PageUp/Down or CTRL-wheel
            v = self.value()
            v *= self._relative_step**(s/copysign(10., v))
            self.setValue(v)
