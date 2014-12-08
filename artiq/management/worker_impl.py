import sys
from inspect import isclass

from artiq.management import pyon
from artiq.management.file_import import file_import
from artiq.language.context import AutoContext
from artiq.management.dpdb import DeviceParamDB


def run(dpdb, file, unit, function):
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
    unit_inst = unit(dpdb)
    f = getattr(unit_inst, function)
    f()


def put_object(obj):
    ds = pyon.encode(obj)
    sys.__stdout__.write(ds)
    sys.__stdout__.write("\n")
    sys.__stdout__.flush()


def main():
    sys.stdout = sys.stderr

    devices = pyon.load_file(sys.argv[1])
    parameters = pyon.load_file(sys.argv[2])
    dpdb = DeviceParamDB(devices, parameters)

    while True:
        line = sys.__stdin__.readline()
        obj = pyon.decode(line)
        put_object("ack")

        try:
            run(dpdb, **obj)
        except Exception as e:
            put_object({"status": "failed", "message": str(e)})
        else:
            put_object({"status": "ok"})

if __name__ == "__main__":
    main()
