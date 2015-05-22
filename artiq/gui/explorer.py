from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget


class ExplorerDock(dockarea.Dock):
    def __init__(self):
        dockarea.Dock.__init__(self, "Explorer", size=(1100, 400))

        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.addWidget(splitter)

        grid = LayoutWidget()
        splitter.addWidget(grid)

        el = QtGui.QListView()
        grid.addWidget(el, 0, 0, colspan=4)

        datetime = QtGui.QDateTimeEdit()
        datetime.setDisplayFormat("MMM d yyyy hh:mm:ss")
        datetime.setCalendarPopup(True)
        datetime.setDate(QtCore.QDate.currentDate())
        datetime_en = QtGui.QCheckBox("Set due date:")
        grid.addWidget(datetime_en, 1, 0)
        grid.addWidget(datetime, 1, 1, colspan=3)

        pipeline = QtGui.QLineEdit()
        pipeline.insert("main")
        grid.addLabel("Pipeline:", 2, 0)
        grid.addWidget(pipeline, 2, 1)

        priority = QtGui.QSpinBox()
        priority.setRange(-99, 99)
        grid.addLabel("Priority:", 2, 2)
        grid.addWidget(priority, 2, 3)

        submit = QtGui.QPushButton("Submit")
        grid.addWidget(submit, 3, 0, colspan=4)

        placeholder = QtGui.QWidget()
        splitter.addWidget(placeholder)
