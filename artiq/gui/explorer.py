from quamash import QtGui
from pyqtgraph import dockarea


class ExplorerDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Explorer", size=(1100, 400))
