import logging
import asyncio
import os
from functools import partial
from collections import OrderedDict

from PyQt5 import QtCore, QtGui, QtWidgets
import h5py

from sipyco import pyon

from artiq.gui.entries import procdesc_to_entry, EntryTreeWidget
from artiq.gui.fuzzy_select import FuzzySelectWidget
from artiq.gui.tools import (LayoutWidget, log_level_to_name, get_open_file_name)
from artiq.tools import parse_devarg_override, unparse_devarg_override


logger = logging.getLogger(__name__)


# Experiment URLs come in two forms:
# 1. repo:<experiment name>
#    (file name and class name to be retrieved from explist)
# 2. file:<class name>@<file name>


class _ArgumentEditor(EntryTreeWidget):
    def __init__(self, manager, dock, expurl):
        self.manager = manager
        self.expurl = expurl

        EntryTreeWidget.__init__(self)

        arguments = self.manager.get_submission_arguments(self.expurl)

        if not arguments:
            self.insertTopLevelItem(0, QtWidgets.QTreeWidgetItem(["No arguments"]))

        for name, argument in arguments.items():
            self.set_argument(name, argument)

        self.quickStyleClicked.connect(dock.submit_clicked)

        recompute_arguments = QtWidgets.QPushButton("Recompute all arguments")
        recompute_arguments.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_BrowserReload))
        recompute_arguments.clicked.connect(dock._recompute_arguments_clicked)

        load_hdf5 = QtWidgets.QPushButton("Load HDF5")
        load_hdf5.setIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_DialogOpenButton))
        load_hdf5.clicked.connect(dock._load_hdf5_clicked)

        buttons = LayoutWidget()
        buttons.addWidget(recompute_arguments, 1, 1)
        buttons.addWidget(load_hdf5, 1, 2)
        buttons.layout.setColumnStretch(0, 1)
        buttons.layout.setColumnStretch(1, 0)
        buttons.layout.setColumnStretch(2, 0)
        buttons.layout.setColumnStretch(3, 1)
        self.setItemWidget(self.bottom_item, 1, buttons)

    def reset_entry(self, key):
        asyncio.ensure_future(self._recompute_argument(key))

    async def _recompute_argument(self, name):
        try:
            expdesc, _ = await self.manager.compute_expdesc(self.expurl)
        except:
            logger.error("Could not recompute argument '%s' of '%s'",
                         name, self.expurl, exc_info=True)
            return
        argument = self.manager.get_submission_arguments(self.expurl)[name]

        procdesc = expdesc["arginfo"][name][0]
        state = procdesc_to_entry(procdesc).default_state(procdesc)
        argument["desc"] = procdesc
        argument["state"] = state
        self.update_argument(name, argument)

    # Hooks that allow user-supplied argument editors to react to imminent user
    # actions. Here, we always keep the manager-stored submission arguments
    # up-to-date, so no further action is required.
    def about_to_submit(self):
        pass

    def about_to_close(self):
        pass


log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class _ExperimentDock(QtWidgets.QMdiSubWindow):
    sigClosed = QtCore.pyqtSignal()

    def __init__(self, manager, expurl):
        QtWidgets.QMdiSubWindow.__init__(self)
        qfm = QtGui.QFontMetrics(self.font())
        self.resize(100 * qfm.averageCharWidth(), 30 * qfm.lineSpacing())
        self.setWindowTitle(expurl)
        self.setWindowIcon(QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_FileDialogContentsView))

        self.layout = QtWidgets.QGridLayout()
        top_widget = QtWidgets.QWidget()
        top_widget.setLayout(self.layout)
        self.setWidget(top_widget)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.manager = manager
        self.expurl = expurl

        editor_class = self.manager.get_argument_editor_class(expurl)
        self.argeditor = editor_class(self.manager, self, self.expurl)
        self.layout.addWidget(self.argeditor, 0, 0, 1, 5)
        self.layout.setRowStretch(0, 1)

        scheduling = manager.get_submission_scheduling(expurl)
        options = manager.get_submission_options(expurl)

        datetime = QtWidgets.QDateTimeEdit()
        datetime.setDisplayFormat("MMM d yyyy hh:mm:ss")
        datetime_en = QtWidgets.QCheckBox("Due date:")
        self.layout.addWidget(datetime_en, 1, 0)
        self.layout.addWidget(datetime, 1, 1)

        if scheduling["due_date"] is None:
            datetime.setDate(QtCore.QDate.currentDate())
        else:
            datetime.setDateTime(QtCore.QDateTime.fromMSecsSinceEpoch(
                int(scheduling["due_date"] * 1000)))
        datetime_en.setChecked(scheduling["due_date"] is not None)

        def update_datetime(dt):
            scheduling["due_date"] = dt.toMSecsSinceEpoch() / 1000
            datetime_en.setChecked(True)
        datetime.dateTimeChanged.connect(update_datetime)

        def update_datetime_en(checked):
            if checked:
                due_date = datetime.dateTime().toMSecsSinceEpoch() / 1000
            else:
                due_date = None
            scheduling["due_date"] = due_date
        datetime_en.stateChanged.connect(update_datetime_en)

        self.pipeline_name = QtWidgets.QLineEdit()
        pipeline_name = self.pipeline_name
        self.layout.addWidget(QtWidgets.QLabel("Pipeline:"), 1, 2)
        self.layout.addWidget(pipeline_name, 1, 3)

        pipeline_name.setText(scheduling["pipeline_name"])

        def update_pipeline_name(text):
            scheduling["pipeline_name"] = text
        pipeline_name.textChanged.connect(update_pipeline_name)

        self.priority = QtWidgets.QSpinBox()
        priority = self.priority
        priority.setRange(-99, 99)
        self.layout.addWidget(QtWidgets.QLabel("Priority:"), 2, 0)
        self.layout.addWidget(priority, 2, 1)

        priority.setValue(scheduling["priority"])

        def update_priority(value):
            scheduling["priority"] = value
        priority.valueChanged.connect(update_priority)

        self.flush = QtWidgets.QCheckBox("Flush")
        flush = self.flush
        flush.setToolTip("Flush the pipeline (of current- and higher-priority "
                         "experiments) before starting the experiment")
        self.layout.addWidget(flush, 2, 2)

        flush.setChecked(scheduling["flush"])

        def update_flush(checked):
            scheduling["flush"] = bool(checked)
        flush.stateChanged.connect(update_flush)

        devarg_override = QtWidgets.QComboBox()
        devarg_override.setEditable(True)
        devarg_override.lineEdit().setPlaceholderText("Override device arguments")
        devarg_override.lineEdit().setClearButtonEnabled(True)
        devarg_override.insertItem(0, "core:analyze_at_run_end=True")
        self.layout.addWidget(devarg_override, 2, 3)

        devarg_override.setCurrentText(options["devarg_override"])

        def update_devarg_override(text):
            options["devarg_override"] = text
        devarg_override.editTextChanged.connect(update_devarg_override)
        self.devarg_override = devarg_override

        log_level = QtWidgets.QComboBox()
        log_level.addItems(log_levels)
        log_level.setCurrentIndex(1)
        log_level.setToolTip("Minimum level for log entry production")
        log_level_label = QtWidgets.QLabel("Logging level:")
        log_level_label.setToolTip("Minimum level for log message production")
        self.layout.addWidget(log_level_label, 3, 0)
        self.layout.addWidget(log_level, 3, 1)

        log_level.setCurrentIndex(log_levels.index(
            log_level_to_name(options["log_level"])))

        def update_log_level(index):
            options["log_level"] = getattr(logging, log_level.currentText())
        log_level.currentIndexChanged.connect(update_log_level)
        self.log_level = log_level

        if "repo_rev" in options:
            repo_rev = QtWidgets.QLineEdit()
            repo_rev.setPlaceholderText("current")
            repo_rev.setClearButtonEnabled(True)
            repo_rev_label = QtWidgets.QLabel("Rev / ref:")
            repo_rev_label.setToolTip("Experiment repository revision "
                                      "(commit ID) or reference (branch "
                                      "or tag) to use")
            self.layout.addWidget(repo_rev_label, 3, 2)
            self.layout.addWidget(repo_rev, 3, 3)

            if options["repo_rev"] is not None:
                repo_rev.setText(options["repo_rev"])

            def update_repo_rev(text):
                if text:
                    options["repo_rev"] = text
                else:
                    options["repo_rev"] = None
            repo_rev.textChanged.connect(update_repo_rev)
            self.repo_rev = repo_rev

        submit = QtWidgets.QPushButton("Submit")
        submit.setIcon(QtWidgets.QApplication.style().standardIcon(
                       QtWidgets.QStyle.SP_DialogOkButton))
        submit.setToolTip("Schedule the experiment (Ctrl+Return)")
        submit.setShortcut("CTRL+RETURN")
        submit.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                             QtWidgets.QSizePolicy.Expanding)
        self.layout.addWidget(submit, 1, 4, 2, 1)
        submit.clicked.connect(self.submit_clicked)

        reqterm = QtWidgets.QPushButton("Terminate instances")
        reqterm.setIcon(QtWidgets.QApplication.style().standardIcon(
                        QtWidgets.QStyle.SP_DialogCancelButton))
        reqterm.setToolTip("Request termination of instances (Ctrl+Backspace)")
        reqterm.setShortcut("CTRL+BACKSPACE")
        reqterm.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                              QtWidgets.QSizePolicy.Expanding)
        self.layout.addWidget(reqterm, 3, 4)
        reqterm.clicked.connect(self.reqterm_clicked)

        self.hdf5_load_directory = os.path.expanduser("~")

    def submit_clicked(self):
        self.argeditor.about_to_submit()
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

    async def _recompute_arguments_task(self, overrides=dict()):
        try:
            expdesc, ui_name = await self.manager.compute_expdesc(self.expurl)
        except:
            logger.error("Could not recompute experiment description of '%s'",
                         self.expurl, exc_info=True)
            return
        arginfo = expdesc["arginfo"]
        for k, v in overrides.items():
            # Some values (e.g. scans) may have multiple defaults in a list
            if ("default" in arginfo[k][0] and isinstance(arginfo[k][0]["default"], list)):
                arginfo[k][0]["default"].insert(0, v)
            else:
                arginfo[k][0]["default"] = v
        self.manager.initialize_submission_arguments(self.expurl, arginfo, ui_name)

        argeditor_state = self.argeditor.save_state()
        self.argeditor.deleteLater()

        editor_class = self.manager.get_argument_editor_class(self.expurl)
        self.argeditor = editor_class(self.manager, self, self.expurl)
        self.layout.addWidget(self.argeditor, 0, 0, 1, 5)
        self.argeditor.restore_state(argeditor_state)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        reset_sched = menu.addAction("Reset scheduler settings")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == reset_sched:
            asyncio.ensure_future(self._recompute_sched_options_task())

    async def _recompute_sched_options_task(self):
        try:
            expdesc, _ = await self.manager.compute_expdesc(self.expurl)
        except:
            logger.error("Could not recompute experiment description of '%s'",
                         self.expurl, exc_info=True)
            return
        sched_defaults = expdesc["scheduler_defaults"]

        scheduling = self.manager.get_submission_scheduling(self.expurl)
        scheduling.update(sched_defaults)
        self.priority.setValue(scheduling["priority"])
        self.pipeline_name.setText(scheduling["pipeline_name"])
        self.flush.setChecked(scheduling["flush"])

    def _load_hdf5_clicked(self):
        asyncio.ensure_future(self._load_hdf5_task())

    async def _load_hdf5_task(self):
        try:
            filename = await get_open_file_name(
                self.manager.main_window, "Load HDF5",
                self.hdf5_load_directory,
                "HDF5 files (*.h5 *.hdf5);;All files (*.*)")
        except asyncio.CancelledError:
            return
        self.hdf5_load_directory = os.path.dirname(filename)

        try:
            with h5py.File(filename, "r") as f:
                expid = f["expid"][()]
            expid = pyon.decode(expid)
            arguments = expid["arguments"]
        except:
            logger.error("Could not retrieve expid from HDF5 file",
                         exc_info=True)
            return

        try:
            if "devarg_override" in expid:
                self.devarg_override.setCurrentText(
                    unparse_devarg_override(expid["devarg_override"]))
            self.log_level.setCurrentIndex(log_levels.index(
                log_level_to_name(expid["log_level"])))
            if "repo_rev" in expid and \
               expid["repo_rev"] != "N/A" and \
               hasattr(self, "repo_rev"):
                self.repo_rev.setText(expid["repo_rev"])
        except:
            logger.error("Could not set submission options from HDF5 expid",
                         exc_info=True)
            return

        await self._recompute_arguments_task(arguments)

    def closeEvent(self, event):
        self.argeditor.about_to_close()
        self.sigClosed.emit()
        QtWidgets.QMdiSubWindow.closeEvent(self, event)

    def save_state(self):
        return {
            "args": self.argeditor.save_state(),
            "geometry": bytes(self.saveGeometry()),
            "hdf5_load_directory": self.hdf5_load_directory
        }

    def restore_state(self, state):
        self.argeditor.restore_state(state["args"])
        self.restoreGeometry(QtCore.QByteArray(state["geometry"]))
        self.hdf5_load_directory = state["hdf5_load_directory"]


class _QuickOpenDialog(QtWidgets.QDialog):
    """Modal dialog for opening/submitting experiments from a
    FuzzySelectWidget."""
    closed = QtCore.pyqtSignal()

    def __init__(self, manager):
        super().__init__(manager.main_window)
        self.setModal(True)

        self.manager = manager

        self.setWindowTitle("Quick open...")

        layout = QtWidgets.QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Find matching experiment names. Open experiments are preferred to
        # matches from the repository to ease quick window switching.
        open_exps = list(self.manager.open_experiments.keys())
        repo_exps = set("repo:" + k
                        for k in self.manager.explist.keys()) - set(open_exps)
        choices = [(o, 100) for o in open_exps] + [(r, 0) for r in repo_exps]

        self.select_widget = FuzzySelectWidget(choices)
        layout.addWidget(self.select_widget)
        self.select_widget.aborted.connect(self.close)
        self.select_widget.finished.connect(self._open_experiment)

        font_metrics = QtGui.QFontMetrics(self.select_widget.line_edit.font())
        self.select_widget.setMinimumWidth(font_metrics.averageCharWidth() * 70)

    def done(self, r):
        if self.select_widget:
            self.select_widget.abort()
        self.closed.emit()
        QtWidgets.QDialog.done(self, r)

    def _open_experiment(self, exp_name, modifiers):
        if modifiers & QtCore.Qt.ControlModifier:
            try:
                self.manager.submit(exp_name)
            except:
                # Not all open_experiments necessarily still exist in the explist
                # (e.g. if the repository has been re-scanned since).
                logger.warning("failed to submit experiment '%s'",
                               exp_name,
                               exc_info=True)
        else:
            self.manager.open_experiment(exp_name)
        self.close()


class ExperimentManager:
    #: Global registry for custom argument editor classes, indexed by the experiment
    #: `argument_ui` string; can be populated by dashboard plugins such as ndscan.
    #: If no handler for a requested UI name is found, the default built-in argument
    #: editor will be used.
    argument_ui_classes = dict()

    def __init__(self, main_window, dataset_sub,
                 explist_sub, schedule_sub,
                 schedule_ctl, experiment_db_ctl):
        self.main_window = main_window
        self.schedule_ctl = schedule_ctl
        self.experiment_db_ctl = experiment_db_ctl

        self.dock_states = dict()
        self.submission_scheduling = dict()
        self.submission_options = dict()
        self.submission_arguments = dict()
        self.argument_ui_names = dict()

        self.datasets = dict()
        dataset_sub.add_setmodel_callback(self.set_dataset_model)
        self.explist = dict()
        explist_sub.add_setmodel_callback(self.set_explist_model)
        self.schedule = dict()
        schedule_sub.add_setmodel_callback(self.set_schedule_model)

        self.open_experiments = dict()

        self.is_quick_open_shown = False
        quick_open_shortcut = QtWidgets.QShortcut(
            QtCore.Qt.CTRL + QtCore.Qt.Key_P,
            main_window)
        quick_open_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        quick_open_shortcut.activated.connect(self.show_quick_open)

    def set_dataset_model(self, model):
        self.datasets = model

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

    def get_argument_editor_class(self, expurl):
        ui_name = self.argument_ui_names.get(expurl, None)
        if not ui_name and expurl[:5] == "repo:":
            ui_name = self.explist.get(expurl[5:], {}).get("argument_ui", None)
        if ui_name:
            result = self.argument_ui_classes.get(ui_name, None)
            if result:
                return result
            logger.warning("Ignoring unknown argument UI '%s'", ui_name)
        return _ArgumentEditor

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
            if expurl[:5] == "repo:":
                scheduling.update(self.explist[expurl[5:]]["scheduler_defaults"])
            self.submission_scheduling[expurl] = scheduling
            return scheduling

    def get_submission_options(self, expurl):
        if expurl in self.submission_options:
            return self.submission_options[expurl]
        else:
            # mutated by _ExperimentDock
            options = {
                "log_level": logging.WARNING,
                "devarg_override": ""
            }
            if expurl[:5] == "repo:":
                options["repo_rev"] = None
            self.submission_options[expurl] = options
            return options

    def initialize_submission_arguments(self, expurl, arginfo, ui_name):
        arguments = OrderedDict()
        for name, (procdesc, group, tooltip) in arginfo.items():
            state = procdesc_to_entry(procdesc).default_state(procdesc)
            arguments[name] = {
                "desc": procdesc,
                "group": group,
                "tooltip": tooltip,
                "state": state,  # mutated by entries
            }
        self.submission_arguments[expurl] = arguments
        self.argument_ui_names[expurl] = ui_name
        return arguments

    def set_argument_value(self, expurl, name, value):
        try:
            argument = self.submission_arguments[expurl][name]
            if argument["desc"]["ty"] == "Scannable":
                ty = value["ty"]
                argument["state"]["selected"] = ty
                argument["state"][ty] = value
            else:
                argument["state"] = value
            if expurl in self.open_experiments.keys():
                self.open_experiments[expurl].argeditor.update_argument(name, argument)
        except:
            logger.warn("Failed to set value for argument \"{}\" in experiment: {}."
                        .format(name, expurl), exc_info=1)

    def get_submission_arguments(self, expurl):
        if expurl in self.submission_arguments:
            return self.submission_arguments[expurl]
        else:
            if expurl[:5] != "repo:":
                raise ValueError("Submission arguments must be preinitialized "
                                 "when not using repository")
            class_desc = self.explist[expurl[5:]]
            return self.initialize_submission_arguments(expurl, class_desc["arginfo"],
                                                        class_desc.get("argument_ui", None))

    def open_experiment(self, expurl):
        if expurl in self.open_experiments:
            dock = self.open_experiments[expurl]
            mdi_area = dock.mdiArea()
            if mdi_area is not None:
                tab_widget = self.main_window.centralWidget()
                tab_widget.setCurrentWidget(mdi_area)
                mdi_area.setActiveSubWindow(dock)

            if dock.isMinimized():
                dock.showNormal()
            return dock
        try:
            dock = _ExperimentDock(self, expurl)
        except Exception:
            logger.warning(
                "Failed to create experiment dock for %s, attempting to reset arguments",
                expurl,
                exc_info=True,
            )
            del self.submission_arguments[expurl]
            dock = _ExperimentDock(self, expurl)
        self.open_experiments[expurl] = dock
        dock.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        mdi_area = self.main_window.centralWidget().currentWidget()
        if mdi_area is not None:
            mdi_area.addSubWindow(dock)
        dock.show()
        dock.sigClosed.connect(partial(self.on_dock_closed, expurl))
        if expurl in self.dock_states:
            try:
                dock.restore_state(self.dock_states[expurl])
            except Exception:
                logger.warning(
                    "Failed to restore dock state when opening experiment %s",
                    expurl,
                    exc_info=True,
                )
        return dock

    def on_dock_closed(self, expurl):
        dock = self.open_experiments[expurl]
        self.dock_states[expurl] = dock.save_state()
        del self.open_experiments[expurl]

    async def _submit_task(self, expurl, *args):
        try:
            rid = await self.schedule_ctl.submit(*args)
        except KeyError:
            expid = args[1]
            logger.error("Submission failed - revision \"%s\" was not found", expid["repo_rev"])
        else:
            logger.info("Submitted '%s', RID is %d", expurl, rid)

    def submit(self, expurl):
        file, class_name, _ = self.resolve_expurl(expurl)
        scheduling = self.get_submission_scheduling(expurl)
        options = self.get_submission_options(expurl)
        arguments = self.get_submission_arguments(expurl)

        argument_values = dict()
        for name, argument in arguments.items():
            entry_cls = procdesc_to_entry(argument["desc"])
            argument_values[name] = entry_cls.state_to_value(argument["state"])

        try:
            devarg_override = parse_devarg_override(options["devarg_override"])
        except:
            logger.error("Failed to parse device argument overrides for %s", expurl)
            return

        expid = {
            "devarg_override": devarg_override,
            "log_level": options["log_level"],
            "file": file,
            "class_name": class_name,
            "arguments": argument_values,
        }
        if "repo_rev" in options:
            expid["repo_rev"] = options["repo_rev"]
        asyncio.ensure_future(self._submit_task(
            expurl,
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
        logger.info(
            "Requesting termination of all instances "
            "of '%s'", expurl)
        file, class_name, use_repository = self.resolve_expurl(expurl)
        rids = []
        for rid, desc in self.schedule.items():
            expid = desc["expid"]
            if use_repository:
                repo_match = "repo_rev" in expid
            else:
                repo_match = "repo_rev" not in expid
            if repo_match and \
               ("file" in expid and expid["file"] == file) and \
               expid["class_name"] == class_name:
                rids.append(rid)
        asyncio.ensure_future(self._request_term_multiple(rids))

    async def compute_expdesc(self, expurl):
        file, class_name, use_repository = self.resolve_expurl(expurl)
        if use_repository:
            revision = self.get_submission_options(expurl)["repo_rev"]
        else:
            revision = None
        description = await self.experiment_db_ctl.examine(
            file, use_repository, revision)
        class_desc = description[class_name]
        return class_desc, class_desc.get("argument_ui", None)

    async def open_file(self, file):
        description = await self.experiment_db_ctl.examine(file, False)
        for class_name, class_desc in description.items():
            expurl = "file:{}@{}".format(class_name, file)
            self.initialize_submission_arguments(expurl, class_desc["arginfo"],
                                                 class_desc.get("argument_ui", None))
            if expurl in self.open_experiments:
                self.open_experiments[expurl].close()
            self.open_experiment(expurl)

    def save_state(self):
        for expurl, dock in self.open_experiments.items():
            self.dock_states[expurl] = dock.save_state()
        experiment_mdi = {}
        for expurl, dock in self.open_experiments.items():
            experiment_mdi[expurl] = dock.mdiArea().tab_name
        return {
            "scheduling": self.submission_scheduling,
            "options": self.submission_options,
            "arguments": self.submission_arguments,
            "docks": self.dock_states,
            "argument_uis": self.argument_ui_names,
            "open_docks": set(self.open_experiments.keys()),
            "experiment_mdi": experiment_mdi
        }

    def restore_state(self, state):
        if self.open_experiments:
            raise NotImplementedError
        self.dock_states = state["docks"]
        self.submission_scheduling = state["scheduling"]
        self.submission_options = state["options"]
        self.submission_arguments = state["arguments"]
        self.argument_ui_names = state.get("argument_uis", {})
        experiment_mdi = state.get("experiment_mdi", {})
        if 'experiment_mdi' in state:
            for expurl in state["open_docks"]:
                tab_widget = self.main_window.centralWidget()
                mdi_area_name = experiment_mdi[expurl]
                mdi_area = self.main_window.get_mdi_area_by_name(mdi_area_name)
                tab_widget.setCurrentWidget(mdi_area)
                self.open_experiment(expurl)
        else:
            # else statement is necessary for migration purpose
            tab_widget = self.main_window.centralWidget()
            mdi_area = self.main_window.new_mdi_area()
            tab_widget.setCurrentWidget(mdi_area)
            for expurl in state["open_docks"]:
                self.open_experiment(expurl)

    def show_quick_open(self):
        if self.is_quick_open_shown:
            return

        self.is_quick_open_shown = True
        dialog = _QuickOpenDialog(self)

        def closed():
            self.is_quick_open_shown = False
        dialog.closed.connect(closed)
        dialog.show()
