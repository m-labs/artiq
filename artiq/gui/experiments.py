import logging
import asyncio
from functools import partial
from collections import OrderedDict

from quamash import QtGui, QtCore

from pyqtgraph import dockarea

from artiq.gui.tools import log_level_to_name, disable_scroll_wheel
from artiq.gui.scan import ScanController


logger = logging.getLogger(__name__)


class _StringEntry(QtGui.QLineEdit):
    def __init__(self, argument):
        QtGui.QLineEdit.__init__(self)
        self.setText(argument["state"])
        def update():
            argument["state"] = self.text()
        self.editingFinished.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        return procdesc.get("default", "")


class _BooleanEntry(QtGui.QCheckBox):
    def __init__(self, argument):
        QtGui.QCheckBox.__init__(self)
        self.setChecked(argument["state"])
        def update(checked):
            argument["state"] = bool(checked)
        self.stateChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        return procdesc.get("default", False)


class _EnumerationEntry(QtGui.QComboBox):
    def __init__(self, argument):
        QtGui.QComboBox.__init__(self)
        disable_scroll_wheel(self)
        choices = argument["desc"]["choices"]
        self.addItems(choices)
        idx = choices.index(argument["state"])
        self.setCurrentIndex(idx)
        def update(index):
            argument["state"] = choices[index]
        self.currentIndexChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        if "default" in procdesc:
            return procdesc["default"]
        else:
            return procdesc["choices"][0]


class _NumberEntry(QtGui.QDoubleSpinBox):
    def __init__(self, argument):
        QtGui.QDoubleSpinBox.__init__(self)
        disable_scroll_wheel(self)
        procdesc = argument["desc"]
        scale = procdesc["scale"]
        self.setDecimals(procdesc["ndecimals"])
        self.setSingleStep(procdesc["step"]/scale)
        if procdesc["min"] is not None:
            self.setMinimum(procdesc["min"]/scale)
        else:
            self.setMinimum(float("-inf"))
        if procdesc["max"] is not None:
            self.setMaximum(procdesc["max"]/scale)
        else:
            self.setMaximum(float("inf"))
        if procdesc["unit"]:
            self.setSuffix(" " + procdesc["unit"])

        self.setValue(argument["state"]/scale)
        def update(value):
            argument["state"] = value*scale
        self.valueChanged.connect(update)

    @staticmethod
    def state_to_value(state):
        return state

    @staticmethod
    def default_state(procdesc):
        if "default" in procdesc:
            return procdesc["default"]
        else:
            return 0.0


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

        for n, (name, argument) in enumerate(arguments.items()):
            entry = _argty_to_entry[argument["desc"]["ty"]](argument)
            self._args_to_entries[name] = entry

            widget_item = QtGui.QTreeWidgetItem([name, ""])
            if argument["group"] is None:
                self.addTopLevelItem(widget_item)
            else:
                self._get_group(argument["group"]).addChild(widget_item)
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

    def save_state(self):
        expanded = []
        for k, v in self._groups.items():
            if v.isExpanded():
                expanded.append(k)
        return {"expanded": expanded}

    def restore_state(self, state):
        for e in state["expanded"]:
            try:
                self._groups[e].setExpanded(True)
            except KeyError:
                pass


class _ExperimentDock(dockarea.Dock):
    def __init__(self, manager, expname):
        dockarea.Dock.__init__(self, "Exp: " + expname,
                               closable=True, size=(1500, 500))
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.manager = manager
        self.expname = expname

        self.argeditor = _ArgumentEditor(
            manager.get_submission_arguments(expname))
        self.addWidget(self.argeditor, 0, 0, colspan=5)

        scheduling = manager.get_submission_scheduling(expname)
        options = manager.get_submission_options(expname)

        datetime = QtGui.QDateTimeEdit()
        datetime.setDisplayFormat("MMM d yyyy hh:mm:ss")
        datetime_en = QtGui.QCheckBox("Due date:")
        self.addWidget(datetime_en, 1, 0)
        self.addWidget(datetime, 1, 1)

        if scheduling["due_date"] is None:
            datetime.setDate(QtCore.QDate.currentDate())
        else:
            datetime.setDateTime(QtCore.QDateTime.fromMSecsSinceEpoch(
                scheduling["due_date"]*1000))
        datetime_en.setChecked(scheduling["due_date"] is not None)
        def update_datetime(dt):
            scheduling["due_date"] = dt.toMSecsSinceEpoch()/1000
            datetime_en.setChecked(True)
        datetime.dateTimeChanged.connect(update_datetime)
        def update_datetime_en(checked):
            if checked:
                due_date = datetime.dateTime().toMSecsSinceEpoch()/1000
            else:
                due_date = None
            scheduling["due_date"] = due_date
        datetime_en.stateChanged.connect(update_datetime_en)

        pipeline_name = QtGui.QLineEdit()
        self.addWidget(QtGui.QLabel("Pipeline:"), 1, 2)
        self.addWidget(pipeline_name, 1, 3)

        pipeline_name.setText(scheduling["pipeline_name"])
        def update_pipeline_name():
            scheduling["pipeline_name"] = pipeline_name.text()
        pipeline_name.editingFinished.connect(update_pipeline_name)

        priority = QtGui.QSpinBox()
        priority.setRange(-99, 99)
        self.addWidget(QtGui.QLabel("Priority:"), 2, 0)
        self.addWidget(priority, 2, 1)

        priority.setValue(scheduling["priority"])
        def update_priority(value):
            scheduling["priority"] = value
        priority.valueChanged.connect(update_priority)

        flush = QtGui.QCheckBox("Flush")
        flush.setToolTip("Flush the pipeline before starting the experiment")
        self.addWidget(flush, 2, 2, colspan=2)

        flush.setChecked(scheduling["flush"])
        def update_flush(checked):
            scheduling["flush"] = bool(checked)
        flush.stateChanged.connect(update_flush)

        log_level = QtGui.QComboBox()
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        log_level.addItems(log_levels)
        log_level.setCurrentIndex(1)
        log_level.setToolTip("Minimum level for log entry production")
        log_level_label = QtGui.QLabel("Logging level:")
        log_level_label.setToolTip("Minimum level for log message production")
        self.addWidget(log_level_label, 3, 0)
        self.addWidget(log_level, 3, 1)

        log_level.setCurrentIndex(log_levels.index(
            log_level_to_name(options["log_level"])))
        def update_log_level(index):
            options["log_level"] = getattr(logging, log_level.currentText())
        log_level.currentIndexChanged.connect(update_log_level)

        repo_rev = QtGui.QLineEdit()
        repo_rev.setPlaceholderText("HEAD")
        repo_rev_label = QtGui.QLabel("Revision:")
        repo_rev_label.setToolTip("Experiment repository revision "
                                  "(commit ID) to use")
        self.addWidget(repo_rev_label, 3, 2)
        self.addWidget(repo_rev, 3, 3)

        if options["repo_rev"] is not None:
            repo_rev.setText(options["repo_rev"])
        def update_repo_rev():
            t = repo_rev.text()
            if t:
                options["repo_rev"] = t
            else:
                options["repo_rev"] = None
        repo_rev.editingFinished.connect(update_repo_rev)

        submit = QtGui.QPushButton("Submit")
        submit.setToolTip("Schedule the selected experiment (Ctrl+Return)")
        submit.setSizePolicy(QtGui.QSizePolicy.Expanding,
                             QtGui.QSizePolicy.Expanding)
        self.addWidget(submit, 1, 4, rowspan=3)
        submit.clicked.connect(self.submit_clicked)

    def submit_clicked(self):
        self.manager.submit(self.expname)

    def save_state(self):
        return self.argeditor.save_state()

    def restore_state(self, state):
        self.argeditor.restore_state(state)


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
            # mutated by _ExperimentDock
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
            # mutated by _ExperimentDock
            options = {
                "log_level": logging.WARNING,
                "repo_rev": None
            }
            self.submission_options[expname] = options
            return options

    def get_submission_arguments(self, expname):
        if expname in self.submission_arguments:
            return self.submission_arguments[expname]
        else:
            arguments = OrderedDict()
            arginfo = self.explist[expname]["arguments"]
            for name, (procdesc, group) in arginfo:
                state = _argty_to_entry[procdesc["ty"]].default_state(procdesc)
                arguments[name] = {
                    "desc": procdesc,
                    "group": group,
                    "state": state  # mutated by entries
                }
            self.submission_arguments[expname] = arguments
            return arguments

    def open_experiment(self, expname):
        if expname in self.open_experiments:
            return self.open_experiments[expname]
        dock = _ExperimentDock(self, expname)
        self.open_experiments[expname] = dock
        self.dock_area.addDock(dock)
        self.dock_area.floatDock(dock)
        dock.sigClosed.connect(partial(self.on_dock_closed, expname))
        return dock

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

        argument_values = dict()
        for name, argument in arguments.items():
            entry_cls = _argty_to_entry[argument["desc"]["ty"]]
            argument_values[name] = entry_cls.state_to_value(argument["state"])

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
        self.status_bar.showMessage("Requesting termination of all instances "
                                    "of '{}'".format(expname))
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
        docks = {expname: dock.save_state()
                 for expname, dock in self.open_experiments.items()}
        return {
            "scheduling": self.submission_scheduling,
            "options": self.submission_options,
            "arguments": self.submission_arguments,
            "docks": docks
        }

    def restore_state(self, state):
        if self.open_experiments:
            raise NotImplementedError
        self.submission_scheduling = state["scheduling"]
        self.submission_options = state["options"]
        self.submission_arguments = state["arguments"]
        for expname, dock_state in state["docks"].items():
            dock = self.open_experiment(expname)
            dock.restore_state(dock_state)
