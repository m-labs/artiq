import re
from PyQt5 import QtGui, QtWidgets

# after
# http://jdreaver.com/posts/2014-07-28-scientific-notation-spin-box-pyside.html


_inf = float("inf")
# Regular expression to find floats. Match groups are the whole string, the
# whole coefficient, the decimal part of the coefficient, and the exponent
# part.
_float_re = re.compile(r"(([+-]?\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)")


def valid_float_string(string):
    match = _float_re.search(string)
    if match:
        return match.groups()[0] == string
    return False


class FloatValidator(QtGui.QValidator):
    def validate(self, string, position):
        if valid_float_string(string):
            return self.Acceptable, string, position
        if string == "" or string[position-1] in "eE.-+":
            return self.Intermediate, string, position
        return self.Invalid, string, position

    def fixup(self, text):
        match = _float_re.search(text)
        if match:
            return match.groups()[0]
        return ""


class ScientificSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimum(-_inf)
        self.setMaximum(_inf)
        self.validator = FloatValidator()
        self.setDecimals(20)

    def validate(self, text, position):
        return self.validator.validate(text, position)

    def fixup(self, text):
        return self.validator.fixup(text)

    def valueFromText(self, text):
        return float(text)

    def textFromValue(self, value):
        return format_float(value)

    def stepBy(self, steps):
        text = self.cleanText()
        groups = _float_re.search(text).groups()
        decimal = float(groups[1])
        decimal += steps
        new_string = "{:g}".format(decimal) + (groups[3] if groups[3] else "")
        self.lineEdit().setText(new_string)


def format_float(value):
    """Modified form of the 'g' format specifier."""
    string = "{:g}".format(value)
    string = string.replace("e+", "e")
    string = re.sub("e(-?)0*(\d+)", r"e\1\2", string)
    return string
