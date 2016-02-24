import sys
import time
import os
import logging
import traceback
from collections import OrderedDict

import artiq
from artiq.protocols import pipe_ipc, pyon
from artiq.tools import multiline_log_config, file_import
from artiq.master.worker_db import DeviceManager, DatasetManager, get_hdf5_output
from artiq.language.environment import is_experiment
from artiq.language.core import set_watchdog_factory, TerminationRequested
from artiq.coredevice.core import CompileError, host_only, _render_diagnostic
from artiq import __version__ as artiq_version


ipc = None

def get_object():
    line = ipc.readline().decode()
    return pyon.decode(line)


def put_object(obj):
    ds = pyon.encode(obj)
    ipc.write((ds + "\n").encode())


class ParentActionError(Exception):
    pass


def make_parent_action(action, exception=None):
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
            if exception is None:
                exn = ParentActionError(reply["exception"])
            else:
                exn = exception(reply["message"])
            exn.parent_traceback = reply["traceback"]
            raise exn
    return parent_action


class ParentDeviceDB:
    get_device_db = make_parent_action("get_device_db")
    get = make_parent_action("get_device", KeyError)


class ParentDatasetDB:
    get = make_parent_action("get_dataset", KeyError)
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
    pause_noexc = staticmethod(make_parent_action("pause"))

    @host_only
    def pause(self):
        if self.pause_noexc():
            raise TerminationRequested

    submit = staticmethod(make_parent_action("scheduler_submit"))
    delete = staticmethod(make_parent_action("scheduler_delete"))
    request_termination = staticmethod(
        make_parent_action("scheduler_request_termination"))
    get_status  = staticmethod(make_parent_action("scheduler_get_status"))

    def set_run_info(self, rid, pipeline_name, expid, priority):
        self.rid = rid
        self.pipeline_name = pipeline_name
        self.expid = expid
        self.priority = priority


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

    def get(name):
        return None


class DummyDatasetMgr:
    def set(key, value, broadcast=False, persist=False, save=True):
        return None

    def get(key):
        pass


def examine(device_mgr, dataset_mgr, file):
    module = file_import(file)
    for class_name, exp_class in module.__dict__.items():
        if class_name[0] == "_":
            continue
        if is_experiment(exp_class):
            if exp_class.__doc__ is None:
                name = class_name
            else:
                name = exp_class.__doc__.splitlines()[0].strip()
                if name[-1] == ".":
                    name = name[:-1]
            exp_inst = exp_class(device_mgr, dataset_mgr,
                                 default_arg_none=True,
                                 enable_processors=True)
            arginfo = OrderedDict(
                (k, (proc.describe(), group))
                for k, (proc, group) in exp_inst.requested_args.items())
            register_experiment(class_name, name, arginfo)


def string_to_hdf5(f, key, value):
    dtype = "S{}".format(len(value))
    dataset = f.create_dataset(key, (), dtype)
    dataset[()] = value.encode()


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
    artiq.coredevice.core._DiagnosticEngine.render_diagnostic = render_diagnostic


def main():
    global ipc

    multiline_log_config(level=int(sys.argv[2]))
    ipc = pipe_ipc.ChildComm(sys.argv[1])

    start_time = None
    rid = None
    expid = None
    exp = None
    exp_inst = None
    repository_path = None

    device_mgr = DeviceManager(ParentDeviceDB,
                               virtual_devices={"scheduler": Scheduler()})
    dataset_mgr = DatasetManager(ParentDatasetDB)

    try:
        while True:
            obj = get_object()
            action = obj["action"]
            if action == "build":
                start_time = time.localtime()
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
                exp_inst = exp(
                    device_mgr, dataset_mgr, enable_processors=True,
                    **expid["arguments"])
                put_object({"action": "completed"})
            elif action == "prepare":
                exp_inst.prepare()
                put_object({"action": "completed"})
            elif action == "run":
                exp_inst.run()
                put_object({"action": "completed"})
            elif action == "analyze":
                exp_inst.analyze()
                put_object({"action": "completed"})
            elif action == "write_results":
                f = get_hdf5_output(start_time, rid, exp.__name__)
                try:
                    dataset_mgr.write_hdf5(f)
                    string_to_hdf5(f, "artiq_version", artiq_version)
                    if "repo_rev" in expid:
                        string_to_hdf5(f, "repo_rev", expid["repo_rev"])
                finally:
                    f.close()
                put_object({"action": "completed"})
            elif action == "examine":
                examine(ExamineDeviceMgr, DummyDatasetMgr, obj["file"])
                put_object({"action": "completed"})
            elif action == "terminate":
                break
    except Exception as exc:
        # When we get CompileError, a more suitable diagnostic has already
        # been printed.
        if not isinstance(exc, CompileError):
            short_exc_info = type(exc).__name__
            exc_str = str(exc)
            if exc_str:
                short_exc_info += ": " + exc_str
            lines = ["Terminating with exception ("+short_exc_info+")\n"]
            if hasattr(exc, "artiq_core_exception"):
                lines.append(str(exc.artiq_core_exception))
            if hasattr(exc, "parent_traceback"):
                lines += exc.parent_traceback
                lines += traceback.format_exception_only(type(exc), exc)
            logging.error("".join(lines).rstrip(),
                          exc_info=not hasattr(exc, "parent_traceback"))
        put_object({"action": "exception"})
    finally:
        device_mgr.close_devices()
        ipc.close()


if __name__ == "__main__":
    main()
