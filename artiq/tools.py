from operator import itemgetter
import importlib.machinery
import linecache
import logging


def format_run_arguments(arguments):
    fmtargs = []
    for k, v in sorted(arguments.items(), key=itemgetter(0)):
        fmtargs.append(k + "=" + str(v))
    if fmtargs:
        return " ".join(fmtargs)
    else:
        return "-"


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


def verbosity_args(parser):
    group = parser.add_argument_group("verbosity")
    group.add_argument("-v", "--verbose", default=0, action="count")
    group.add_argument("-q", "--quiet", default=0, action="count")


def init_logger(args, **kwargs):
    logging.basicConfig(level=logging.WARNING + args.quiet*10 - args.verbose*10, **kwargs)
