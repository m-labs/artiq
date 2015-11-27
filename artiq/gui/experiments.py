import logging
import asyncio
from functools import partial
from collections import OrderedDict

from quamash import QtGui, QtCore

from pyqtgraph import dockarea

from artiq.gui.scan import ScanController


logger = logging.getLogger(__name__)


class _StringEntry(QtGui.QLineEdit):
    def __init__(self, argdesc):
        QtGui.QLineEdit.__init__(self)

    @staticmethod
    def default(argdesc):
        return ""

    def get_argument_value(self):
        return self.text()

    def set_argument_value(self, value):
        self.setText(value)


class _BooleanEntry(QtGui.QCheckBox):
    def __init__(self, argdesc):
        QtGui.QCheckBox.__init__(self)

    @staticmethod
    def default(argdesc):
        return False

    def get_argument_value(self):
        return self.isChecked()

    def set_argument_value(self, value):
        self.setChecked(value)


class _EnumerationEntry(QtGui.QComboBox):
    def __init__(self, argdesc):
        QtGui.QComboBox.__init__(self)
        self.choices = argdesc["choices"]
        self.addItems(self.choices)

    @staticmethod
    def default(argdesc):
        return argdesc["choices"][0]

    def get_argument_value(self):
        return self.choices[self.currentIndex()]

    def set_argument_value(self, value):
        idx = self.choices.index(value)
        self.setCurrentIndex(idx)


class _NumberEntry(QtGui.QDoubleSpinBox):
    def __init__(self, argdesc):
        QtGui.QDoubleSpinBox.__init__(self)
        self.scale = argdesc["scale"]
        self.setDecimals(argdesc["ndecimals"])
        self.setSingleStep(argdesc["step"]/self.scale)
        if argdesc["min"] is not None:
            self.setMinimum(argdesc["min"]/self.scale)
        else:
            self.setMinimum(float("-inf"))
        if argdesc["max"] is not None:
            self.setMaximum(argdesc["max"]/self.scale)
        else:
            self.setMaximum(float("inf"))
        if argdesc["unit"]:
            self.setSuffix(" " + argdesc["unit"])
        
    @staticmethod
    def default(argdesc):
        return 0.0

    def get_argument_value(self):
        return self.value()*self.scale

    def set_argument_value(self, value):
        self.setValue(value/self.scale)


_argty_to_entry = {
    "PYONValue": _StringEntry,
    "BooleanValue": _BooleanEntry,
    "EnumerationValue": _EnumerationEntry,
    "NumberValue": _NumberEntry,
    "StringValue": _StringEntry,
    "Scannable": ScanController
}


class _ArgumentEditor(QtGui.QTreeWidget):
    def __init__(self, arguments):
        QtGui.QTreeWidget.__init__(self)
        self.setColumnCount(2)
        self.header().setResizeMode(QtGui.QHeaderView.ResizeToContents)
        self.header().setVisible(False)
        self.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.setHorizontalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)

        self._groups = dict()
        self._args_to_entries = dict()

        if not arguments:
            self.addTopLevelItem(QtGui.QTreeWidgetItem(["No arguments", ""]))

        for n, (name, (argdesc, group, value)) in enumerate(arguments.items()):
            entry = _argty_to_entry[argdesc["ty"]](argdesc)
            entry.set_argument_value(value)
            self._args_to_entries[name] = entry

            widget_item = QtGui.QTreeWidgetItem([name, ""])
            if group is None:
                self.addTopLevelItem(widget_item)
            else:
                self._get_group(group).addChild(widget_item)
            self.setItemWidget(widget_item, 1, entry)

    def _get_group(self, name):
        if name in self._groups:
            return self._groups[name]
        group = QtGui.QTreeWidgetItem([name, ""])
        for c in 0, 1:
            group.setBackground(c, QtGui.QBrush(QtGui.QColor(100, 100, 100)))
            group.setForeground(c, QtGui.QBrush(QtGui.QColor(220, 220, 255)))
            font = group.font(c)
            font.setBold(True)
            group.setFont(c, font)
        self.addTopLevelItem(group)
        self._groups[name] = group
        return group

    def get_argument_values(self):
        return {arg: entry.get_argument_value()
                for arg, entry in self._args_to_entries.items()}

    def save_state(self):
        expanded = []
        for k, v in self._groups.items():
            if v.isExpanded():
                expanded.append(k)
        argument_values = self.get_argument_values()
        return {
            "expanded": expanded,
            "argument_values": argument_values
        }

    def restore_state(self, state):
        for arg, value in state["argument_values"].items():
            try:
                entry = self._args_to_entries[arg]
                entry.set_argument_value(value)
            except:
                logger.warning("failed to restore value of argument %s", arg,
                               exc_info=True)
        for e in state["expanded"]:
            try:
                self._groups[e].setExpanded(True)
            except KeyError:
                pass


class _ExperimentDock(dockarea.Dock):
    def __init__(self, manager, expname):
        dockarea.Dock.__init__(self, "Experiment: " + expname,
                               closable=True, size=(1500, 500))
        self.manager = manager
        self.expname = expname

        self.argeditor = _ArgumentEditor(
            manager.get_submission_arguments(expname))
        self.addWidget(self.argeditor, 0, 0, colspan=4)

        self.datetime = QtGui.QDateTimeEdit()
        self.datetime.setDisplayFormat("MMM d yyyy hh:mm:ss")
        self.datetime.setDate(QtCore.QDate.currentDate())
        self.datetime.dateTimeChanged.connect(
            lambda: self.datetime_en.setChecked(True))
        self.datetime_en = QtGui.QCheckBox("Due date:")
        self.addWidget(self.datetime_en, 1, 0, colspan=2)
        self.addWidget(self.datetime, 1, 2, colspan=2)

        self.pipeline = QtGui.QLineEdit()
        self.pipeline.setText("main")
        self.addWidget(QtGui.QLabel("Pipeline:"), 2, 0, colspan=2)
        self.addWidget(self.pipeline, 2, 2, colspan=2)

        self.priority = QtGui.QSpinBox()
        self.priority.setRange(-99, 99)
        self.addWidget(QtGui.QLabel("Priority:"), 3, 0)
        self.addWidget(self.priority, 3, 1)

        self.flush = QtGui.QCheckBox("Flush")
        self.flush.setToolTip("Flush the pipeline before starting the experiment")
        self.addWidget(self.flush, 3, 2)

        self.log_level = QtGui.QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.setCurrentIndex(1)
        self.log_level.setToolTip("Minimum level for log entry production")
        self.addWidget(self.log_level, 3, 3)

        submit = QtGui.QPushButton("Submit")
        submit.setToolTip("Schedule the selected experiment (Ctrl+Return)")
        self.addWidget(submit, 4, 0, colspan=4)
        submit.clicked.connect(self.submit_clicked)

    def submit_clicked(self):
        self.manager.submit(self.expname)


class ExperimentManager:
    def __init__(self, status_bar, dock_area,
                 explist_sub, schedule_sub,
                 schedule_ctl):
        self.status_bar = status_bar
        self.dock_area = dock_area
        self.schedule_ctl = schedule_ctl

        self.submission_scheduling = dict()
        self.submission_options = dict()
        self.submission_arguments = dict()

        self.explist = dict()
        explist_sub.add_setmodel_callback(self.set_explist_model)
        self.schedule = dict()
        schedule_sub.add_setmodel_callback(self.set_schedule_model)

        self.open_experiments = dict()

    def set_explist_model(self, model):
        self.explist = model.backing_store

    def set_schedule_model(self, model):
        self.schedule = model.backing_store

    def get_submission_scheduling(self, expname):
        if expname in self.submission_scheduling:
            return self.submission_scheduling[expname]
        else:
            scheduling = {
                "pipeline_name": "main",
                "priority": 0,
                "due_date": None,
                "flush": False
            }
            self.submission_scheduling[expname] = scheduling
            return scheduling

    def get_submission_options(self, expname):
        if expname in self.submission_options:
            return self.submission_options[expname]
        else:
            options = {
                "log_level": logging.WARNING,
                "repo_rev": None
            }
            self.submission_options = options
            return options

    def get_submission_arguments(self, expname):
        if expname in self.submission_arguments:
            return self.submission_arguments[expname]
        else:
            arguments = OrderedDict()
            arginfo = self.explist[expname]["arguments"]
            for name, (procdesc, group) in arginfo:
                argdesc = dict(procdesc)
                if "default" in argdesc:
                    value = argdesc["default"]
                    del argdesc["default"]
                else:
                    value = _argty_to_entry[argdesc["ty"]].default(argdesc)
                arguments[name] = argdesc, group, value
            self.submission_arguments[expname] = arguments
            return arguments

    def open_experiment(self, expname):
        if expname in self.open_experiments:
            return
        dock = _ExperimentDock(self, expname)
        self.open_experiments[expname] = dock
        self.dock_area.addDock(dock)
        self.dock_area.floatDock(dock)
        dock.sigClosed.connect(partial(self.on_dock_closed, expname))

    def on_dock_closed(self, expname):
        del self.open_experiments[expname]

    async def _submit_task(self, *args):
        rid = await self.schedule_ctl.submit(*args)
        self.status_bar.showMessage("Submitted RID {}".format(rid))

    def submit(self, expname):
        expinfo = self.explist[expname]
        scheduling = self.get_submission_scheduling(expname)
        options = self.get_submission_options(expname)
        arguments = self.get_submission_arguments(expname)
        argument_values = {k: v[2] for k, v in arguments.items()}

        expid = {
            "log_level": options["log_level"],
            "repo_rev": options["repo_rev"],
            "file": expinfo["file"],
            "class_name": expinfo["class_name"],
            "arguments": argument_values,
        }
        asyncio.ensure_future(self._submit_task(
            scheduling["pipeline_name"],
            expid,
            scheduling["priority"], scheduling["due_date"],
            scheduling["flush"]))

    async def _request_term_multiple(self, rids):
        for rid in rids:
            try:
                await self.schedule_ctl.request_termination(rid)
            except:
                # May happen if the experiment has terminated by itself
                # while we were terminating others.
                logger.debug("failed to request termination of RID %d",
                             rid, exc_info=True)

    def request_inst_term(self, expname):
        expinfo = self.explist[expname]
        rids = []
        for rid, desc in self.schedule.items():
            expid = desc["expid"]
            if ("repo_rev" in expid  # only consider runs from repository
                    and expid["file"] == expinfo["file"]
                    and expid["class_name"] == expinfo["class_name"]):
                rids.append(rid)
        asyncio.ensure_future(self._request_term_multiple(rids))

    def save_state(self):
        return dict()

    def restore_state(self):
        if self.open_experiments:
            raise NotImplementedError
