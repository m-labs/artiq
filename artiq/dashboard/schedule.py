import asyncio
import time
from functools import partial
import logging

from PyQt5 import QtCore, QtWidgets, QtGui

from artiq.gui.models import DictSyncModel
from artiq.tools import elide


logger = logging.getLogger(__name__)


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


class ScheduleDock(QtWidgets.QDockWidget):
    def __init__(self, schedule_ctl, schedule_sub):
        QtWidgets.QDockWidget.__init__(self, "Schedule")
        self.setObjectName("Schedule")
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

        self.schedule_ctl = schedule_ctl

        self.table = QtWidgets.QTableView()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.setWidget(self.table)

        self.table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        request_termination_action = QtWidgets.QAction("Request termination", self.table)
        request_termination_action.triggered.connect(partial(self.delete_clicked, True))
        request_termination_action.setShortcut("DELETE")
        request_termination_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        self.table.addAction(request_termination_action)
        delete_action = QtWidgets.QAction("Delete", self.table)
        delete_action.triggered.connect(partial(self.delete_clicked, False))
        delete_action.setShortcut("SHIFT+DELETE")
        delete_action.setShortcutContext(QtCore.Qt.WidgetShortcut)
        self.table.addAction(delete_action)
        terminate_pipeline = QtWidgets.QAction(
            "Gracefully terminate all in pipeline", self.table)
        terminate_pipeline.triggered.connect(self.terminate_pipeline_clicked)
        self.table.addAction(terminate_pipeline)

        self.table_model = Model(dict())
        schedule_sub.add_setmodel_callback(self.set_model)

        cw = QtGui.QFontMetrics(self.font()).averageCharWidth()
        h = self.table.horizontalHeader()
        h.resizeSection(0, 7*cw)
        h.resizeSection(1, 12*cw)
        h.resizeSection(2, 16*cw)
        h.resizeSection(3, 6*cw)
        h.resizeSection(4, 16*cw)
        h.resizeSection(5, 30*cw)
        h.resizeSection(6, 20*cw)
        h.resizeSection(7, 20*cw)

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
                logger.info("Requested termination of RID %d", rid)
            else:
                logger.info("Deleted RID %d", rid)
            asyncio.ensure_future(self.delete(rid, graceful))

    async def request_term_multiple(self, rids):
        for rid in rids:
            try:
                await self.schedule_ctl.request_termination(rid)
            except:
                # May happen if the experiment has terminated by itself
                # while we were terminating others.
                logger.debug("failed to request termination of RID %d",
                             rid, exc_info=True)

    def terminate_pipeline_clicked(self):
        idx = self.table.selectedIndexes()
        if idx:
            row = idx[0].row()
            selected_rid = self.table_model.row_to_key[row]
            pipeline = self.table_model.backing_store[selected_rid]["pipeline"]
            logger.info("Requesting termination of all "
                "experiments in pipeline '%s'", pipeline)

            rids = set()
            for rid, info in self.table_model.backing_store.items():
                if info["pipeline"] == pipeline:
                    rids.add(rid)
            asyncio.ensure_future(self.request_term_multiple(rids))


    def save_state(self):
        return bytes(self.table.horizontalHeader().saveState())

    def restore_state(self, state):
        self.table.horizontalHeader().restoreState(QtCore.QByteArray(state))
