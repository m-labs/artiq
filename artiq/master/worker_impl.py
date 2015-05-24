import sys
import time

from artiq.protocols import pyon
from artiq.tools import file_import
from artiq.master.worker_db import DBHub, ResultDB
from artiq.master.results import get_hdf5_output
from artiq.language.experiment import is_experiment
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


class ParentDDB:
    request = make_parent_action("req_device", "name", KeyError)


class ParentPDB:
    request = make_parent_action("req_parameter", "name", KeyError)
    set = make_parent_action("set_parameter", "name value")


init_rt_results = make_parent_action("init_rt_results", "description")
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
        "pipeline_name expid priority due_date"))
    cancel = staticmethod(make_parent_action("scheduler_cancel", "rid"))

    def __init__(self, pipeline_name, expid, priority):
        self.pipeline_name = pipeline_name
        self.expid = expid
        self.priority = priority


def get_exp(file, exp):
    module = file_import(file)
    if exp is None:
        exps = [v for k, v in module.__dict__.items()
                if is_experiment(v)]
        if len(exps) != 1:
            raise ValueError("Found {} experiments in module"
                             .format(len(exps)))
        return exps[0]
    else:
        return getattr(module, exp)


def main():
    sys.stdout = sys.stderr

    start_time = None
    rid = None
    expid = None
    exp = None
    exp_inst = None

    rdb = ResultDB(init_rt_results, update_rt_results)
    dbh = DBHub(ParentDDB, ParentPDB, rdb)

    try:
        while True:
            obj = get_object()
            action = obj["action"]
            if action == "prepare":
                start_time = time.localtime()
                rid = obj["rid"]
                pipeline_name = obj["pipeline_name"]
                expid = obj["expid"]
                priority = obj["priority"]
                exp = get_exp(expid["file"], expid["experiment"])
                exp_inst = exp(dbh,
                               scheduler=Scheduler(pipeline_name,
                                                   expid,
                                                   priority),
                               **expid["arguments"])
                rdb.build()
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
            elif action == "terminate":
                break
    finally:
        dbh.close_devices()

if __name__ == "__main__":
    main()
