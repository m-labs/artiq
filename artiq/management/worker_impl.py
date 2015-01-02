import sys
from inspect import isclass
import traceback

from artiq.management import pyon
from artiq.management.file_import import file_import
from artiq.language.context import AutoContext
from artiq.management.dpdb import DeviceParamSupplier


def run(dps, file, unit):
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
    unit_inst = unit(dps)
    unit_inst.run()


def get_object():
    line = sys.__stdin__.readline()
    return pyon.decode(line)


def put_object(obj):
    ds = pyon.encode(obj)
    sys.__stdout__.write(ds)
    sys.__stdout__.write("\n")
    sys.__stdout__.flush()


def req_device(name):
    put_object({"action": "req_device", "name": name})
    obj = get_object()
    if obj["status"] == "ok":
        return obj["data"]
    else:
        raise KeyError


def req_parameter(name):
    put_object({"action": "req_parameter", "name": name})
    obj = get_object()
    if obj["status"] == "ok":
        return obj["data"]
    else:
        raise KeyError


def main():
    sys.stdout = sys.stderr

    dps = DeviceParamSupplier(req_device, req_parameter)

    while True:
        obj = get_object()
        put_object("ack")

        try:
            try:
                run(dps, **obj)
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
