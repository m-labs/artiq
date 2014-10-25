import sys
import importlib

from artiq.management import pyon


def import_in_folder(path, name):
    try:
        del sys.modules[name]  # force path search
    except KeyError:
        pass
    loader = importlib.find_loader(name, [path])
    if loader is None:
        raise ImportError("Could not find loader")
    return loader.load_module()


def run(path, name):
    module = import_in_folder(path, name)
    module.main()


def put_object(obj):
    ds = pyon.encode(obj)
    sys.__stdout__.write(ds)
    sys.__stdout__.write("\n")
    sys.__stdout__.flush()


def main():
    sys.stdout = sys.stderr

    while True:
        line = sys.__stdin__.readline()
        obj = pyon.decode(line)
        put_object("ack")

        try:
            run(**obj)
        except Exception as e:
            put_object({"status": "failed", "message": str(e)})
        else:
            put_object({"status": "ok"})

if __name__ == "__main__":
    main()
