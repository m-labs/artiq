import sys
from inspect import isclass
import traceback

from artiq.management import pyon
from artiq.management.file_import import file_import
from artiq.language.context import AutoContext
from artiq.management.dpdb import DeviceParamSupplier


def run(dps, file, unit, arguments):
    module = file_import(file)
    if unit is None:
        units = [v for k, v in module.__dict__.items()
                 if k[0] != "_"
                    and isclass(v)
                    and issubclass(v, AutoContext)
                    and v is not AutoContext]
        if len(units) != 1:
            raise ValueError("Found {} units in module".format(len(units)))
        unit = units[0]
    else:
        unit = getattr(module, unit)
    unit_inst = unit(dps, **arguments)
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
            raise exception
    return parent_action


req_device = make_parent_action("req_device", "name", KeyError)
req_parameter = make_parent_action("req_parameter", "name", KeyError)
set_parameter = make_parent_action("set_parameter", "name value")


def main():
    sys.stdout = sys.stderr

    while True:
        obj = get_object()
        put_object("ack")

        dps = DeviceParamSupplier(req_device, req_parameter)
        try:
            try:
                run(dps, **obj)
                for requester, name in dps.parameter_wb:
                    set_parameter(name, getattr(requester, name))
            except Exception:
                put_object({"action": "report_completed",
                            "status": "failed",
                            "message": traceback.format_exc()})
            else:
                put_object({"action": "report_completed",
                            "status": "ok"})
        finally:
            dps.close()

if __name__ == "__main__":
    main()
