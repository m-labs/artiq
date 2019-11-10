"""Worker process implementation.

This module contains the worker process main() function and the glue code
necessary to connect the global artefacts used from experiment code (scheduler,
device database, etc.) to their actual implementation in the parent master
process via IPC.
"""

import sys
import time
import os
import logging
import traceback
from collections import OrderedDict

import h5py

from sipyco import pipe_ipc, pyon
from sipyco.packed_exceptions import raise_packed_exc
from sipyco.logging_tools import multiline_log_config

import artiq
from artiq.tools import file_import
from artiq.master.worker_db import DeviceManager, DatasetManager, DummyDevice
from artiq.language.environment import (is_experiment, TraceArgumentManager,
                                        ProcessArgumentManager)
from artiq.language.core import set_watchdog_factory, TerminationRequested
from artiq.language.types import TBool
from artiq.compiler import import_cache
from artiq.coredevice.core import CompileError, host_only, _render_diagnostic
from artiq import __version__ as artiq_version


ipc = None


def get_object():
    line = ipc.readline().decode()
    return pyon.decode(line)


def put_object(obj):
    ds = pyon.encode(obj)
    ipc.write((ds + "\n").encode())


def make_parent_action(action):
    def parent_action(*args, **kwargs):
        request = {"action": action, "args": args, "kwargs": kwargs}
        put_object(request)
        reply = get_object()
        if "action" in reply:
            if reply["action"] == "terminate":
                sys.exit()
            else:
                raise ValueError
        if reply["status"] == "ok":
            return reply["data"]
        else:
            raise_packed_exc(reply["exception"])
    return parent_action


class ParentDeviceDB:
    get_device_db = make_parent_action("get_device_db")
    get = make_parent_action("get_device")


class ParentDatasetDB:
    get = make_parent_action("get_dataset")
    update = make_parent_action("update_dataset")


class Watchdog:
    _create = make_parent_action("create_watchdog")
    _delete = make_parent_action("delete_watchdog")

    def __init__(self, t):
        self.t = t

    def __enter__(self):
        self.wid = Watchdog._create(self.t)

    def __exit__(self, type, value, traceback):
        Watchdog._delete(self.wid)


set_watchdog_factory(Watchdog)


class Scheduler:
    def set_run_info(self, rid, pipeline_name, expid, priority):
        self.rid = rid
        self.pipeline_name = pipeline_name
        self.expid = expid
        self.priority = priority

    pause_noexc = staticmethod(make_parent_action("pause"))
    @host_only
    def pause(self):
        if self.pause_noexc():
            raise TerminationRequested

    _check_pause = staticmethod(make_parent_action("scheduler_check_pause"))
    def check_pause(self, rid=None) -> TBool:
        if rid is None:
            rid = self.rid
        return self._check_pause(rid)

    _submit = staticmethod(make_parent_action("scheduler_submit"))
    def submit(self, pipeline_name=None, expid=None, priority=None, due_date=None, flush=False):
        if pipeline_name is None:
            pipeline_name = self.pipeline_name
        if expid is None:
            expid = self.expid
        if priority is None:
            priority = self.priority
        return self._submit(pipeline_name, expid, priority, due_date, flush)

    delete = staticmethod(make_parent_action("scheduler_delete"))
    request_termination = staticmethod(
        make_parent_action("scheduler_request_termination"))
    get_status = staticmethod(make_parent_action("scheduler_get_status"))


class CCB:
    issue = staticmethod(make_parent_action("ccb_issue"))


def get_exp(file, class_name):
    module = file_import(file, prefix="artiq_worker_")
    if class_name is None:
        exps = [v for k, v in module.__dict__.items()
                if is_experiment(v)]
        if len(exps) != 1:
            raise ValueError("Found {} experiments in module"
                             .format(len(exps)))
        return exps[0]
    else:
        return getattr(module, class_name)


register_experiment = make_parent_action("register_experiment")


class ExamineDeviceMgr:
    get_device_db = make_parent_action("get_device_db")

    @staticmethod
    def get(name):
        return DummyDevice()


class ExamineDatasetMgr:
    @staticmethod
    def get(key, archive=False):
        return ParentDatasetDB.get(key)

    @staticmethod
    def update(self, mod):
        pass


def examine(device_mgr, dataset_mgr, file):
    previous_keys = set(sys.modules.keys())
    try:
        module = file_import(file)
        for class_name, exp_class in module.__dict__.items():
            if class_name[0] == "_":
                continue
            if is_experiment(exp_class):
                if exp_class.__doc__ is None:
                    name = class_name
                else:
                    name = exp_class.__doc__.strip().splitlines()[0].strip()
                    if name[-1] == ".":
                        name = name[:-1]
                argument_mgr = TraceArgumentManager()
                scheduler_defaults = {}
                cls = exp_class((device_mgr, dataset_mgr, argument_mgr, scheduler_defaults))
                arginfo = OrderedDict(
                    (k, (proc.describe(), group, tooltip))
                    for k, (proc, group, tooltip) in argument_mgr.requested_args.items())
                register_experiment(class_name, name, arginfo, scheduler_defaults)
    finally:
        new_keys = set(sys.modules.keys())
        for key in new_keys - previous_keys:
            del sys.modules[key]


def setup_diagnostics(experiment_file, repository_path):
    def render_diagnostic(self, diagnostic):
        message = "While compiling {}\n".format(experiment_file) + \
                    _render_diagnostic(diagnostic, colored=False)
        if repository_path is not None:
            message = message.replace(repository_path, "<repository>")

        if diagnostic.level == "warning":
            logging.warn(message)
        else:
            logging.error(message)

    # This is kind of gross, but 1) we do not have any explicit connection
    # between the worker and a coredevice.core.Core instance at all,
    # and 2) the diagnostic engine really ought to be per-Core, since
    # that's what uses it and the repository path is per-Core.
    # So I don't know how to implement this properly for now.
    #
    # This hack is as good or bad as any other solution that involves
    # putting inherently local objects (the diagnostic engine) into
    # global slots, and there isn't any point in making it prettier by
    # wrapping it in layers of indirection.
    artiq.coredevice.core._DiagnosticEngine.render_diagnostic = \
        render_diagnostic

def put_exception_report():
    _, exc, _ = sys.exc_info()
    # When we get CompileError, a more suitable diagnostic has already
    # been printed.
    if not isinstance(exc, CompileError):
        short_exc_info = type(exc).__name__
        exc_str = str(exc)
        if exc_str:
            short_exc_info += ": " + exc_str.splitlines()[0]
        lines = ["Terminating with exception ("+short_exc_info+")\n"]
        if hasattr(exc, "artiq_core_exception"):
            lines.append(str(exc.artiq_core_exception))
        if hasattr(exc, "parent_traceback"):
            lines += exc.parent_traceback
            lines += traceback.format_exception_only(type(exc), exc)
        logging.error("".join(lines).rstrip(),
                      exc_info=not hasattr(exc, "parent_traceback"))
    put_object({"action": "exception"})


def main():
    global ipc

    multiline_log_config(level=int(sys.argv[2]))
    ipc = pipe_ipc.ChildComm(sys.argv[1])

    start_time = None
    run_time = None
    rid = None
    expid = None
    exp = None
    exp_inst = None
    repository_path = None

    device_mgr = DeviceManager(ParentDeviceDB,
                               virtual_devices={"scheduler": Scheduler(),
                                                "ccb": CCB()})
    dataset_mgr = DatasetManager(ParentDatasetDB)

    import_cache.install_hook()

    try:
        while True:
            obj = get_object()
            action = obj["action"]
            if action == "build":
                start_time = time.time()
                rid = obj["rid"]
                expid = obj["expid"]
                if obj["wd"] is not None:
                    # Using repository
                    experiment_file = os.path.join(obj["wd"], expid["file"])
                    repository_path = obj["wd"]
                else:
                    experiment_file = expid["file"]
                    repository_path = None
                setup_diagnostics(experiment_file, repository_path)
                exp = get_exp(experiment_file, expid["class_name"])
                device_mgr.virtual_devices["scheduler"].set_run_info(
                    rid, obj["pipeline_name"], expid, obj["priority"])
                start_local_time = time.localtime(start_time)
                dirname = os.path.join("results",
                                   time.strftime("%Y-%m-%d", start_local_time),
                                   time.strftime("%H", start_local_time))
                os.makedirs(dirname, exist_ok=True)
                os.chdir(dirname)
                argument_mgr = ProcessArgumentManager(expid["arguments"])
                exp_inst = exp((device_mgr, dataset_mgr, argument_mgr, {}))
                put_object({"action": "completed"})
            elif action == "prepare":
                exp_inst.prepare()
                put_object({"action": "completed"})
            elif action == "run":
                run_time = time.time()
                exp_inst.run()
                put_object({"action": "completed"})
            elif action == "analyze":
                try:
                    exp_inst.analyze()
                except:
                    # make analyze failure non-fatal, as we may still want to
                    # write results afterwards
                    put_exception_report()
                else:
                    put_object({"action": "completed"})
            elif action == "write_results":
                filename = "{:09}-{}.h5".format(rid, exp.__name__)
                with h5py.File(filename, "w") as f:
                    dataset_mgr.write_hdf5(f)
                    f["artiq_version"] = artiq_version
                    f["rid"] = rid
                    f["start_time"] = start_time
                    f["run_time"] = run_time
                    f["expid"] = pyon.encode(expid)
                put_object({"action": "completed"})
            elif action == "examine":
                examine(ExamineDeviceMgr, ExamineDatasetMgr, obj["file"])
                put_object({"action": "completed"})
            elif action == "terminate":
                break
    except:
        put_exception_report()
    finally:
        device_mgr.close_devices()
        ipc.close()


if __name__ == "__main__":
    main()
