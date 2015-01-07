import importlib.machinery
import linecache


def file_import(filename):
    linecache.checkcache(filename)

    modname = filename
    i = modname.rfind("/")
    if i > 0:
        modname = modname[i+1:]
    i = modname.find(".")
    if i > 0:
        modname = modname[:i]
    modname = "file_import_" + modname

    loader = importlib.machinery.SourceFileLoader(modname, filename)
    return loader.load_module()
