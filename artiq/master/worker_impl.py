import sys
import time
import os
import logging
from collections import OrderedDict

from artiq.protocols import pyon
from artiq.tools import file_import
from artiq.master.worker_db import DeviceManager, DatasetManager, get_hdf5_output
from artiq.language.environment import is_experiment
from artiq.language.core import set_watchdog_factory, TerminationRequested
from artiq.coredevice.core import CompileError
from artiq import __version__ as artiq_version


def get_object():
    line = sys.__stdin__.readline()
    return pyon.decode(line)


def put_object(obj):
    ds = pyon.encode(obj)
    sys.__stdout__.write(ds)
    sys.__stdout__.write("\n")
    sys.__stdout__.flush()


class ParentActionError(Exception):
    pass


def make_parent_action(action, exception=ParentActionError):
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
            raise exception(reply["message"])
    return parent_action


class LogForwarder:
    def __init__(self):
        self.buffer = ""

    to_parent = staticmethod(make_parent_action("log"))

    def write(self, data):
        self.buffer += data
        while "\n" in self.buffer:
            i = self.buffer.index("\n")
            self.to_parent(self.buffer[:i])
            self.buffer = self.buffer[i+1:]

    def flush(self):
        pass


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


def main():
    sys.stdout = LogForwarder()
    sys.stderr = LogForwarder()
    logging.basicConfig(level=int(sys.argv[1]))

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
    except CompileError as exc:
        # TODO: This should be replaced with a proper DiagnosticEngine.
        message = "Cannot compile {}\n".format(experiment_file) + exc.render_string()
        if repository_path is not None:
            message = message.replace(repository_path, "<repository>")
        logging.error(message)
    except Exception as exc:
        short_exc_info = type(exc).__name__
        exc_str = str(exc)
        if exc_str:
            short_exc_info += ": " + exc_str
        logging.error("Terminating with exception (%s)",
                      short_exc_info, exc_info=True)
    finally:
        device_mgr.close_devices()


if __name__ == "__main__":
    main()
