import sys
from inspect import isclass
import traceback

import h5py

from artiq.protocols import pyon
from artiq.tools import file_import
from artiq.master.db import DBHub, ResultDB


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


def publish_rt_results(notifier, data):
    update_rt_results(data)


class Scheduler:
    run_queued = make_parent_action("scheduler_run_queued", "run_params")
    cancel_queued = make_parent_action("scheduler_cancel_queued", "rid")
    run_timed = make_parent_action("scheduler_run_timed",
                                   "run_params next_run")
    cancel_timed = make_parent_action("scheduler_cancel_timed", "trid")


def get_unit(file, unit):
    module = file_import(file)
    if unit is None:
        units = [v for k, v in module.__dict__.items()
                 if k[0] != "_"
                    and isclass(v)
                    and hasattr(v, "__artiq_unit__")]
        if len(units) != 1:
            raise ValueError("Found {} units in module".format(len(units)))
        return units[0]
    else:
        return getattr(module, unit)


def run(run_params):
    unit = get_unit(run_params["file"], run_params["unit"])

    realtime_results = unit.realtime_results()
    init_rt_results(realtime_results)

    realtime_results_set = set()
    for rr in realtime_results.keys():
        if isinstance(rr, tuple):
            for e in rr:
                realtime_results_set.add(e)
        else:
            realtime_results_set.add(rr)
    rdb = ResultDB(realtime_results_set)
    rdb.realtime_data.publish = publish_rt_results

    dbh = DBHub(ParentDDB, ParentPDB, rdb)
    try:
        try:
            unit_inst = unit(dbh,
                             scheduler=Scheduler,
                             run_params=run_params,
                             **run_params["arguments"])
            unit_inst.run()
            if hasattr(unit_inst, "analyze"):
                unit_inst.analyze()
        except Exception:
            put_object({"action": "report_completed",
                        "status": "failed",
                        "message": traceback.format_exc()})
        else:
            put_object({"action": "report_completed",
                        "status": "ok"})
    finally:
        dbh.close()

    filename = run_params["file"] + ".h5"
    f = h5py.File(filename, "w")
    try:
        rdb.write_hdf5(f)
    finally:
        f.close()


def main():
    sys.stdout = sys.stderr

    while True:
        obj = get_object()
        put_object("ack")
        run(obj)

if __name__ == "__main__":
    main()
