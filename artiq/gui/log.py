from quamash import QtGui
from pyqtgraph import dockarea


class LogDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Log", size=(1000, 300))
