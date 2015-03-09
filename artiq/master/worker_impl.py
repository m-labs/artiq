import sys
import time

from artiq.protocols import pyon
from artiq.tools import file_import
from artiq.master.worker_db import DBHub, ResultDB
from artiq.master.results import get_hdf5_output


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


class Scheduler:
    run_queued = make_parent_action("scheduler_run_queued", "run_params")
    cancel_queued = make_parent_action("scheduler_cancel_queued", "rid")
    run_timed = make_parent_action("scheduler_run_timed",
                                   "run_params next_run")
    cancel_timed = make_parent_action("scheduler_cancel_timed", "trid")


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
    run_params = None
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
                run_params = obj["run_params"]
                exp = get_exp(run_params["file"], run_params["experiment"])
                exp_inst = exp(dbh,
                               scheduler=Scheduler,
                               run_params=run_params,
                               **run_params["arguments"])
                put_object({"action": "completed"})
            elif action == "run":
                exp_inst.run()
                put_object({"action": "completed"})
            elif action == "analyze":
                exp_inst.analyze()
                f = get_hdf5_output(start_time, rid, exp.__name__)
                try:
                    rdb.write_hdf5(f)
                finally:
                    f.close()
                put_object({"action": "completed"})
            elif action == "terminate":
                break
    finally:
        dbh.close()

if __name__ == "__main__":
    main()
