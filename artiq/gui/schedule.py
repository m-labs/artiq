import asyncio
import time

from quamash import QtGui, QtCore
from pyqtgraph import dockarea

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import DictSyncModel


class _ScheduleModel(DictSyncModel):
    def __init__(self, parent, init):
        DictSyncModel.__init__(self,
            ["RID", "Pipeline", "Status", "Prio", "Due date",
             "File", "Class name"],
            parent, init)

    def sort_key(self, k, v):
        # order by priority, and then by due date and RID
        return (-v["priority"], v["due_date"] or 0, k)

    def convert(self, k, v, column):
        if column == 0:
            return k
        elif column == 1:
            return v["pipeline"]
        elif column == 2:
            return v["status"]
        elif column == 3:
            return str(v["priority"])
        elif column == 4:
            if v["due_date"] is None:
                return ""
            else:
                return time.strftime("%m/%d %H:%M:%S",
                                     time.localtime(v["due_date"]))
        elif column == 5:
            return v["expid"]["file"]
        elif column == 6:
            if v["expid"]["class_name"] is None:
                return ""
            else:
                return v["expid"]["class_name"]
        else:
            raise ValueError


class ScheduleDock(dockarea.Dock):
    def __init__(self, status_bar, schedule_ctl):
        dockarea.Dock.__init__(self, "Schedule", size=(1000, 300))

        self.status_bar = status_bar
        self.schedule_ctl = schedule_ctl

        self.table = QtGui.QTableView()
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.addWidget(self.table)

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        delete_action = QtGui.QAction("Delete", self.table)
        delete_action.triggered.connect(self.delete_clicked)
        self.table.addAction(delete_action)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.subscriber = Subscriber("schedule", self.init_schedule_model)
        yield from self.subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.subscriber.close()

    def init_schedule_model(self, init):
        self.table_model = _ScheduleModel(self.table, init)
        self.table.setModel(self.table_model)
        return self.table_model

    @asyncio.coroutine
    def delete(self, rid):
        yield from self.schedule_ctl.delete(rid)

    def delete_clicked(self):
        idx = self.table.selectedIndexes()
        if idx:
            row = idx[0].row()
            rid = self.table_model.row_to_key[row]
            self.status_bar.showMessage("Deleted RID {}".format(rid))
            asyncio.async(self.delete(rid))
