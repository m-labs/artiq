import asyncio

from quamash import QtGui, QtCore
from pyqtgraph import dockarea
from pyqtgraph import LayoutWidget

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import DictSyncModel


class _ExplistModel(DictSyncModel):
    def __init__(self, parent, init):
        DictSyncModel.__init__(self,
            ["Experiment"],
            parent, init)

    def sort_key(self, k, v):
        return k

    def convert(self, k, v, column):
        return k


class ExplorerDock(dockarea.Dock):
    def __init__(self, status_bar, schedule_ctl):
        dockarea.Dock.__init__(self, "Explorer", size=(1500, 500))

        self.status_bar = status_bar
        self.schedule_ctl = schedule_ctl

        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.addWidget(splitter)

        grid = LayoutWidget()
        splitter.addWidget(grid)

        self.el = QtGui.QListView()
        grid.addWidget(self.el, 0, 0, colspan=4)

        self.datetime = QtGui.QDateTimeEdit()
        self.datetime.setDisplayFormat("MMM d yyyy hh:mm:ss")
        self.datetime.setCalendarPopup(True)
        self.datetime.setDate(QtCore.QDate.currentDate())
        self.datetime.dateTimeChanged.connect(self.enable_duedate)
        self.datetime_en = QtGui.QCheckBox("Due date:")
        grid.addWidget(self.datetime_en, 1, 0)
        grid.addWidget(self.datetime, 1, 1)

        self.priority = QtGui.QSpinBox()
        self.priority.setRange(-99, 99)
        grid.addWidget(QtGui.QLabel("Priority:"), 1, 2)
        grid.addWidget(self.priority, 1, 3)

        self.pipeline = QtGui.QLineEdit()
        self.pipeline.insert("main")
        grid.addWidget(QtGui.QLabel("Pipeline:"), 2, 0)
        grid.addWidget(self.pipeline, 2, 1)

        self.flush = QtGui.QCheckBox("Flush")
        grid.addWidget(self.flush, 2, 2, colspan=2)

        submit = QtGui.QPushButton("Submit")
        grid.addWidget(submit, 3, 0, colspan=4)
        submit.clicked.connect(self.submit_clicked)

        placeholder = QtGui.QWidget()
        splitter.addWidget(placeholder)

    def enable_duedate(self):
        self.datetime_en.setChecked(True)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.explist_subscriber = Subscriber("explist",
                                             self.init_explist_model)
        yield from self.explist_subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.explist_subscriber.close()

    def init_explist_model(self, init):
        self.explist_model = _ExplistModel(self.el, init)
        self.el.setModel(self.explist_model)
        return self.explist_model

    @asyncio.coroutine
    def submit(self, pipeline_name, file, experiment, arguments,
               priority, due_date, flush):
        expid = {
            "file": file,
            "experiment": experiment,
            "arguments": arguments,
        }
        rid = yield from self.schedule_ctl.submit(pipeline_name, expid,
                                                  priority, due_date, flush)
        self.status_bar.showMessage("Submitted RID {}".format(rid))

    def submit_clicked(self):
        idx = self.el.selectedIndexes()
        if idx:
            row = idx[0].row()
            key = self.explist_model.row_to_key[row]
            expinfo = self.explist_model.data[key]
            if self.datetime_en.isChecked():
                due_date = self.datetime.dateTime().toMSecsSinceEpoch()/1000
            else:
                due_date = None
            asyncio.async(self.submit(self.pipeline.text(),
                                      expinfo["file"], expinfo["experiment"],
                                      dict(), self.priority.value(), due_date,
                                      self.flush.isChecked()))
