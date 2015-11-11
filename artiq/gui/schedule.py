import asyncio
import time
from functools import partial

from quamash import QtGui, QtCore
from pyqtgraph import dockarea

from artiq.gui.models import DictSyncModel
from artiq.tools import elide


class Model(DictSyncModel):
    def __init__(self, init):
        DictSyncModel.__init__(self,
            ["RID", "Pipeline", "Status", "Prio", "Due date",
             "Revision", "File", "Class name"],
            init)

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
            expid = v["expid"]
            if "repo_rev" in expid:
                r = expid["repo_rev"]
                if v["repo_msg"]:
                    r += "\n" + elide(v["repo_msg"], 40)
                return r
            else:
                return "Outside repo."
        elif column == 6:
            return v["expid"]["file"]
        elif column == 7:
            if v["expid"]["class_name"] is None:
                return ""
            else:
                return v["expid"]["class_name"]
        else:
            raise ValueError


class ScheduleDock(dockarea.Dock):
    def __init__(self, status_bar, schedule_ctl, schedule_sub):
        dockarea.Dock.__init__(self, "Schedule", size=(1000, 300))

        self.status_bar = status_bar
        self.schedule_ctl = schedule_ctl

        self.table = QtGui.QTableView()
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.addWidget(self.table)

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        request_termination_action = QtGui.QAction("Request termination", self.table)
        request_termination_action.triggered.connect(partial(self.delete_clicked, True))
        request_termination_action.setShortcut("DELETE")
        self.table.addAction(request_termination_action)
        delete_action = QtGui.QAction("Delete", self.table)
        delete_action.triggered.connect(partial(self.delete_clicked, False))
        delete_action.setShortcut("SHIFT+DELETE")
        self.table.addAction(delete_action)

        self.table_model = Model(dict())
        schedule_sub.add_setmodel_callback(self.set_model)

    def set_model(self, model):
        self.table_model = model
        self.table.setModel(self.table_model)

    async def delete(self, rid, graceful):
        if graceful:
            await self.schedule_ctl.request_termination(rid)
        else:
            await self.schedule_ctl.delete(rid)

    def delete_clicked(self, graceful):
        idx = self.table.selectedIndexes()
        if idx:
            row = idx[0].row()
            rid = self.table_model.row_to_key[row]
            if graceful:
                msg = "Requested termination of RID {}".format(rid)
            else:
                msg = "Deleted RID {}".format(rid)
            self.status_bar.showMessage(msg)
            asyncio.ensure_future(self.delete(rid, graceful))
