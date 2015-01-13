import sys
from inspect import isclass
import traceback

from artiq.management import pyon
from artiq.management.file_import import file_import
from artiq.language.db import AutoDB
from artiq.management.db import DBHub, ResultDB


def run(dbh, file, unit, arguments):
    module = file_import(file)
    if unit is None:
        units = [v for k, v in module.__dict__.items()
                 if k[0] != "_"
                    and isclass(v)
                    and issubclass(v, AutoDB)
                    and v is not AutoDB]
        if len(units) != 1:
            raise ValueError("Found {} units in module".format(len(units)))
        unit = units[0]
    else:
        unit = getattr(module, unit)
    unit_inst = unit(dbh, **arguments)
    unit_inst.run()


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


def main():
    sys.stdout = sys.stderr

    while True:
        obj = get_object()
        put_object("ack")

        rdb = ResultDB()
        dbh = DBHub(ParentDDB, ParentPDB, rdb)
        try:
            try:
                run(dbh, **obj)
            except Exception:
                put_object({"action": "report_completed",
                            "status": "failed",
                            "message": traceback.format_exc()})
            else:
                put_object({"action": "report_completed",
                            "status": "ok"})
        finally:
            dbh.close()

if __name__ == "__main__":
    main()
