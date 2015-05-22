from quamash import QtGui
from pyqtgraph import dockarea


class ConsoleDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Console", size=(1000, 300))
