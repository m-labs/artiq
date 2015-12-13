import logging
import asyncio
from functools import partial
from collections import OrderedDict

from quamash import QtGui, QtCore

from pyqtgraph import dockarea, LayoutWidget

from artiq.gui.tools import log_level_to_name, disable_scroll_wheel
from artiq.gui.scan import ScanController


logger = logging.getLogger(__name__)


class _StringEntry(QtGui.QLineEdit):
    def __init__(self, argument):
        QtGui.QLineEdit.__init__(self)
        self.setText(argument["state"])
        def update(text):
            argument["state"] = text
        self.textEdited.connect(update)

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


# Experiment URLs come in two forms:
# 1. repo:<experiment name>
#    (file name and class name to be retrieved from explist)
# 2. file:<class name>@<file name>


class _ArgumentEditor(QtGui.QTreeWidget):
    def __init__(self, manager, dock, expurl):
        self.manager = manager
        self.expurl = expurl

        QtGui.QTreeWidget.__init__(self)
        self.setColumnCount(3)
        self.header().setStretchLastSection(False)
        if hasattr(self.header(), "setSectionResizeMode"):
            set_resize_mode = self.header().setSectionResizeMode
        else:
            set_resize_mode = self.header().setResizeMode
        set_resize_mode(0, QtGui.QHeaderView.ResizeToContents)
        set_resize_mode(1, QtGui.QHeaderView.Stretch)
        set_resize_mode(2, QtGui.QHeaderView.ResizeToContents)
        self.header().setVisible(False)
        self.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.setHorizontalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)

        self._groups = dict()
        self._arg_to_entry_widgetitem = dict()

        arguments = self.manager.get_submission_arguments(self.expurl)

        if not arguments:
            self.addTopLevelItem(QtGui.QTreeWidgetItem(["No arguments"]))

        for name, argument in arguments.items():
            entry = _argty_to_entry[argument["desc"]["ty"]](argument)
            widget_item = QtGui.QTreeWidgetItem([name])
            self._arg_to_entry_widgetitem[name] = entry, widget_item

            if argument["group"] is None:
                self.addTopLevelItem(widget_item)
            else:
                self._get_group(argument["group"]).addChild(widget_item)
            self.setItemWidget(widget_item, 1, entry)
            recompute_argument = QtGui.QToolButton()
            recompute_argument.setToolTip("Re-run the experiment's build "
                                          "method and take the default value")
            recompute_argument.setIcon(QtGui.QApplication.style().standardIcon(
                QtGui.QStyle.SP_BrowserReload))
            recompute_argument.clicked.connect(
                partial(self._recompute_argument_clicked, name))
            fix_layout = LayoutWidget()
            fix_layout.addWidget(recompute_argument)
            self.setItemWidget(widget_item, 2, fix_layout)

        widget_item = QtGui.QTreeWidgetItem()
        self.addTopLevelItem(widget_item)
        recompute_arguments = QtGui.QPushButton("Recompute all arguments")
        recompute_arguments.setIcon(QtGui.QApplication.style().standardIcon(
            QtGui.QStyle.SP_BrowserReload))
        recompute_arguments.setSizePolicy(QtGui.QSizePolicy.Maximum,
                                          QtGui.QSizePolicy.Maximum)
        recompute_arguments.clicked.connect(dock._recompute_arguments_clicked)
        fix_layout = LayoutWidget()
        fix_layout.addWidget(recompute_arguments)
        self.setItemWidget(widget_item, 1, fix_layout)

    def _get_group(self, name):
        if name in self._groups:
            return self._groups[name]
        group = QtGui.QTreeWidgetItem([name])
        for c in 0, 1:
            group.setBackground(c, QtGui.QBrush(QtGui.QColor(100, 100, 100)))
            group.setForeground(c, QtGui.QBrush(QtGui.QColor(220, 220, 255)))
            font = group.font(c)
            font.setBold(True)
            group.setFont(c, font)
        self.addTopLevelItem(group)
        self._groups[name] = group
        return group

    def _recompute_argument_clicked(self, name):
        asyncio.ensure_future(self._recompute_argument(name))

    async def _recompute_argument(self, name):
        try:
            arginfo = await self.manager.compute_arginfo(self.expurl)
        except:
            logger.error("Could not recompute argument '%s' of '%s'",
                         name, self.expurl, exc_info=True)
        argument = self.manager.get_submission_arguments(self.expurl)[name]

        procdesc = arginfo[name][0]
        state = _argty_to_entry[procdesc["ty"]].default_state(procdesc)
        argument["desc"] = procdesc
        argument["state"] = state

        old_entry, widget_item = self._arg_to_entry_widgetitem[name]
        old_entry.deleteLater()

        entry = _argty_to_entry[procdesc["ty"]](argument)
        self._arg_to_entry_widgetitem[name] = entry, widget_item
        self.setItemWidget(widget_item, 1, entry)

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
    def __init__(self, manager, expurl):
        dockarea.Dock.__init__(self, "Exp: " + expurl, closable=True)
        self.setMinimumSize(QtCore.QSize(1100, 700))
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.manager = manager
        self.expurl = expurl

        self.argeditor = _ArgumentEditor(self.manager, self, self.expurl)
        self.addWidget(self.argeditor, 0, 0, colspan=5)
        self.layout.setRowStretch(0, 1)

        scheduling = manager.get_submission_scheduling(expurl)
        options = manager.get_submission_options(expurl)

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
        def update_pipeline_name(text):
            scheduling["pipeline_name"] = text
        pipeline_name.textEdited.connect(update_pipeline_name)

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

        if "repo_rev" in options:
            repo_rev = QtGui.QLineEdit()
            repo_rev.setPlaceholderText("current")
            repo_rev_label = QtGui.QLabel("Revision:")
            repo_rev_label.setToolTip("Experiment repository revision "
                                      "(commit ID) to use")
            self.addWidget(repo_rev_label, 3, 2)
            self.addWidget(repo_rev, 3, 3)

            if options["repo_rev"] is not None:
                repo_rev.setText(options["repo_rev"])
            def update_repo_rev(text):
                if text:
                    options["repo_rev"] = text
                else:
                    options["repo_rev"] = None
            repo_rev.textEdited.connect(update_repo_rev)

        submit = QtGui.QPushButton("Submit")
        submit.setIcon(QtGui.QApplication.style().standardIcon(
                QtGui.QStyle.SP_DialogOkButton))
        submit.setToolTip("Schedule the experiment (Ctrl+Return)")
        submit.setShortcut("CTRL+RETURN")
        submit.setSizePolicy(QtGui.QSizePolicy.Expanding,
                             QtGui.QSizePolicy.Expanding)
        self.addWidget(submit, 1, 4, rowspan=2)
        submit.clicked.connect(self.submit_clicked)

        reqterm = QtGui.QPushButton("Terminate instances")
        reqterm.setIcon(QtGui.QApplication.style().standardIcon(
                QtGui.QStyle.SP_DialogCancelButton))
        reqterm.setToolTip("Request termination of instances (Ctrl+Backspace)")
        reqterm.setShortcut("CTRL+BACKSPACE")
        reqterm.setSizePolicy(QtGui.QSizePolicy.Expanding,
                              QtGui.QSizePolicy.Expanding)
        self.addWidget(reqterm, 3, 4)
        reqterm.clicked.connect(self.reqterm_clicked)

    def submit_clicked(self):
        try:
            self.manager.submit(self.expurl)
        except:
            # May happen when experiment has been removed
            # from repository/explist
            logger.error("Failed to submit '%s'",
                         self.expurl, exc_info=True)

    def reqterm_clicked(self):
        try:
            self.manager.request_inst_term(self.expurl)
        except:
            # May happen when experiment has been removed
            # from repository/explist
            logger.error("Failed to request termination of instances of '%s'",
                         self.expurl, exc_info=True)

    def _recompute_arguments_clicked(self):
        asyncio.ensure_future(self._recompute_arguments_task())

    async def _recompute_arguments_task(self):
        try:
            arginfo = await self.manager.compute_arginfo(self.expurl)
        except:
            logger.error("Could not recompute arguments of '%s'",
                         self.expurl, exc_info=True)
        self.manager.initialize_submission_arguments(self.expurl, arginfo)

        self.argeditor.deleteLater()
        self.argeditor = _ArgumentEditor(self.manager, self, self.expurl)
        self.addWidget(self.argeditor, 0, 0, colspan=5)

    def save_state(self):
        return self.argeditor.save_state()

    def restore_state(self, state):
        self.argeditor.restore_state(state)


class ExperimentManager:
    def __init__(self, status_bar, dock_area,
                 explist_sub, schedule_sub,
                 schedule_ctl, experiment_db_ctl):
        self.status_bar = status_bar
        self.dock_area = dock_area
        self.schedule_ctl = schedule_ctl
        self.experiment_db_ctl = experiment_db_ctl

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

    def resolve_expurl(self, expurl):
        if expurl[:5] == "repo:":
            expinfo = self.explist[expurl[5:]]
            return expinfo["file"], expinfo["class_name"], True
        elif expurl[:5] == "file:":
            class_name, file = expurl[5:].split("@", maxsplit=1)
            return file, class_name, False
        else:
            raise ValueError("Malformed experiment URL")

    def get_submission_scheduling(self, expurl):
        if expurl in self.submission_scheduling:
            return self.submission_scheduling[expurl]
        else:
            # mutated by _ExperimentDock
            scheduling = {
                "pipeline_name": "main",
                "priority": 0,
                "due_date": None,
                "flush": False
            }
            self.submission_scheduling[expurl] = scheduling
            return scheduling

    def get_submission_options(self, expurl):
        if expurl in self.submission_options:
            return self.submission_options[expurl]
        else:
            # mutated by _ExperimentDock
            options = {
                "log_level": logging.WARNING
            }
            if expurl[:5] == "repo:":
                options["repo_rev"] = None
            self.submission_options[expurl] = options
            return options

    def initialize_submission_arguments(self, expurl, arginfo):
        arguments = OrderedDict()
        for name, (procdesc, group) in arginfo.items():
            state = _argty_to_entry[procdesc["ty"]].default_state(procdesc)
            arguments[name] = {
                "desc": procdesc,
                "group": group,
                "state": state  # mutated by entries
            }
        self.submission_arguments[expurl] = arguments
        return arguments

    def get_submission_arguments(self, expurl):
        if expurl in self.submission_arguments:
            return self.submission_arguments[expurl]
        else:
            if expurl[:5] != "repo:":
                raise ValueError("Submission arguments must be preinitialized "
                                 "when not using repository")
            arginfo = self.explist[expurl[5:]]["arginfo"]
            arguments = self.initialize_submission_arguments(expurl, arginfo)
            return arguments

    def open_experiment(self, expurl):
        if expurl in self.open_experiments:
            return self.open_experiments[expurl]
        dock = _ExperimentDock(self, expurl)
        self.open_experiments[expurl] = dock
        self.dock_area.floatDock(dock)
        dock.sigClosed.connect(partial(self.on_dock_closed, expurl))
        return dock

    def on_dock_closed(self, expurl):
        del self.open_experiments[expurl]

    async def _submit_task(self, *args):
        rid = await self.schedule_ctl.submit(*args)
        self.status_bar.showMessage("Submitted RID {}".format(rid))

    def submit(self, expurl):
        file, class_name, _ = self.resolve_expurl(expurl)
        scheduling = self.get_submission_scheduling(expurl)
        options = self.get_submission_options(expurl)
        arguments = self.get_submission_arguments(expurl)

        argument_values = dict()
        for name, argument in arguments.items():
            entry_cls = _argty_to_entry[argument["desc"]["ty"]]
            argument_values[name] = entry_cls.state_to_value(argument["state"])

        expid = {
            "log_level": options["log_level"],
            "file": file,
            "class_name": class_name,
            "arguments": argument_values,
        }
        if "repo_rev" in options:
            expid["repo_rev"] = options["repo_rev"]
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

    def request_inst_term(self, expurl):
        self.status_bar.showMessage("Requesting termination of all instances "
                                    "of '{}'".format(expurl))
        file, class_name, use_repository = self.resolve_expurl(expurl)
        rids = []
        for rid, desc in self.schedule.items():
            expid = desc["expid"]
            if use_repository:
                repo_match = "repo_rev" in expid
            else:
                repo_match = "repo_rev" not in expid
            if (repo_match
                    and expid["file"] == file
                    and expid["class_name"] == class_name):
                rids.append(rid)
        asyncio.ensure_future(self._request_term_multiple(rids))

    async def compute_arginfo(self, expurl):
        file, class_name, use_repository = self.resolve_expurl(expurl)
        description = await self.experiment_db_ctl.examine(file,
                                                           use_repository)
        return description[class_name]["arginfo"]

    async def open_file(self, file):
        description = await self.experiment_db_ctl.examine(file, False)
        for class_name, class_desc in description.items():
            expurl = "file:{}@{}".format(class_name, file)
            self.initialize_submission_arguments(expurl, class_desc["arginfo"])
            if expurl in self.open_experiments:
                self.open_experiments[expurl].close()
            self.open_experiment(expurl)

    def save_state(self):
        docks = {expurl: dock.save_state()
                 for expurl, dock in self.open_experiments.items()}
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
        for expurl, dock_state in state["docks"].items():
            dock = self.open_experiment(expurl)
            dock.restore_state(dock_state)
