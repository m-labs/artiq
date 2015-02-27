from operator import itemgetter
import importlib.machinery
import linecache
import logging
import sys
import os.path


def format_arguments(arguments):
    fmtargs = []
    for k, v in sorted(arguments.items(), key=itemgetter(0)):
        fmtargs.append(k + "=" + repr(v))
    if fmtargs:
        return ", ".join(fmtargs)
    else:
        return ""


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

    path = os.path.dirname(os.path.realpath(filename))
    sys.path.insert(0, path)

    loader = importlib.machinery.SourceFileLoader(modname, filename)
    module = loader.load_module()

    sys.path.remove(path)

    return module


def verbosity_args(parser):
    group = parser.add_argument_group("verbosity")
    group.add_argument("-v", "--verbose", default=0, action="count",
                       help="increase logging level")
    group.add_argument("-q", "--quiet", default=0, action="count",
                       help="decrease logging level")


def simple_network_args(parser, default_port):
    group = parser.add_argument_group("network")
    group.add_argument("--bind", default="::1",
                       help="hostname or IP address to bind to")
    group.add_argument("-p", "--port", default=default_port, type=int,
                       help="TCP port to listen to (default: {})"
                       .format(default_port))


def init_logger(args):
    logging.basicConfig(level=logging.WARNING + args.quiet*10 - args.verbose*10)
