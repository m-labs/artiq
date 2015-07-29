import sys
import time

from artiq.protocols import pyon
from artiq.tools import file_import
from artiq.master.worker_db import DeviceManager, ResultDB, get_hdf5_output
from artiq.language.environment import is_experiment
from artiq.language.core import set_watchdog_factory


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


def make_parent_action(action, argnames, exception=ParentActionError):
    argnames = argnames.split()
    def parent_action(*args):
        request = {"action": action}
        for argname, arg in zip(argnames, args):
            request[argname] = arg
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

    to_parent = staticmethod(make_parent_action("log", "message"))

    def write(self, data):
        self.buffer += data
        while "\n" in self.buffer:
            i = self.buffer.index("\n")
            self.to_parent(self.buffer[:i])
            self.buffer = self.buffer[i+1:]

    def flush(self):
        pass


class ParentDDB:
    get = make_parent_action("get_device", "name", KeyError)


class ParentPDB:
    get = make_parent_action("get_parameter", "name", KeyError)
    set = make_parent_action("set_parameter", "name value")


update_rt_results = make_parent_action("update_rt_results", "mod")


class Watchdog:
    _create = make_parent_action("create_watchdog", "t")
    _delete = make_parent_action("delete_watchdog", "wid")

    def __init__(self, t):
        self.t = t

    def __enter__(self):
        self.wid = Watchdog._create(self.t)

    def __exit__(self, type, value, traceback):
        Watchdog._delete(self.wid)


set_watchdog_factory(Watchdog)


class Scheduler:
    pause = staticmethod(make_parent_action("pause", ""))

    submit = staticmethod(make_parent_action("scheduler_submit",
        "pipeline_name expid priority due_date flush"))
    cancel = staticmethod(make_parent_action("scheduler_cancel", "rid"))

    def set_run_info(self, pipeline_name, expid, priority):
        self.pipeline_name = pipeline_name
        self.expid = expid
        self.priority = priority


def get_exp(file, class_name):
    module = file_import(file)
    if class_name is None:
        exps = [v for k, v in module.__dict__.items()
                if is_experiment(v)]
        if len(exps) != 1:
            raise ValueError("Found {} experiments in module"
                             .format(len(exps)))
        return exps[0]
    else:
        return getattr(module, class_name)


register_experiment = make_parent_action("register_experiment",
                                         "class_name name arguments")


class DummyDMGR:
    def get(self, name):
        return None


class DummyPDB:
    def get(self, name):
        return None

    def set(self, name, value):
        pass


def examine(dmgr, pdb, rdb, file):
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
            exp_inst = exp_class(dmgr, pdb, rdb, default_arg_none=True)
            arguments = [(k, v.describe())
                         for k, v in exp_inst.requested_args.items()]
            register_experiment(class_name, name, arguments)


def main():
    sys.stdout = sys.stderr = LogForwarder()

    start_time = None
    rid = None
    expid = None
    exp = None
    exp_inst = None

    dmgr = DeviceManager(ParentDDB,
                         virtual_devices={"scheduler": Scheduler()})
    rdb = ResultDB()
    rdb.rt.publish = update_rt_results

    try:
        while True:
            obj = get_object()
            action = obj["action"]
            if action == "build":
                start_time = time.localtime()
                rid = obj["rid"]
                expid = obj["expid"]
                exp = get_exp(expid["file"], expid["class_name"])
                dmgr.virtual_devices["scheduler"].set_run_info(
                    obj["pipeline_name"], expid, obj["priority"])
                exp_inst = exp(dmgr, ParentPDB, rdb,
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
                    rdb.write_hdf5(f)
                finally:
                    f.close()
                put_object({"action": "completed"})
            elif action == "examine":
                examine(DummyDMGR(), DummyPDB(), ResultDB(), obj["file"])
                put_object({"action": "completed"})
            elif action == "terminate":
                break
    finally:
        dmgr.close_devices()

if __name__ == "__main__":
    main()
