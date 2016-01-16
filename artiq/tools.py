from operator import itemgetter
import importlib.machinery
import linecache
import logging
import sys
import asyncio
import time
import collections
import os
import atexit
import string

import numpy as np

from artiq.language.environment import is_experiment
from artiq.protocols import pyon


__all__ = ["artiq_dir", "parse_arguments", "elide", "short_format", "file_import",
           "get_experiment", "verbosity_args", "simple_network_args", "init_logger",
           "bind_address_from_args", "atexit_register_coroutine",
           "exc_to_warning", "asyncio_wait_or_cancel",
           "TaskObject", "Condition", "get_windows_drives"]


logger = logging.getLogger(__name__)

artiq_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)))


def parse_arguments(arguments):
    d = {}
    for argument in arguments:
        name, eq, value = argument.partition("=")
        d[name] = pyon.decode(value)
    return d


def elide(s, maxlen):
    elided = False
    if len(s) > maxlen:
        s = s[:maxlen]
        elided = True
    try:
        idx = s.index("\n")
    except ValueError:
        pass
    else:
        s = s[:idx]
        elided = True
    if elided:
        maxlen -= 3
        if len(s) > maxlen:
            s = s[:maxlen]
        s += "..."
    return s


def short_format(v):
    if v is None:
        return "None"
    t = type(v)
    if t is bool or np.issubdtype(t, int) or np.issubdtype(t, float):
        return str(v)
    elif t is str:
        return "\"" + elide(v, 50) + "\""
    else:
        r = t.__name__
        if t is list or t is dict or t is set:
            r += " ({})".format(len(v))
        if t is np.ndarray:
            r += " " + str(np.shape(v))
        return r


def file_import(filename, prefix="file_import_"):
    linecache.checkcache(filename)

    modname = filename
    i = modname.rfind("/")
    if i > 0:
        modname = modname[i+1:]
    i = modname.find(".")
    if i > 0:
        modname = modname[:i]
    modname = prefix + modname

    path = os.path.dirname(os.path.realpath(filename))
    sys.path.insert(0, path)

    loader = importlib.machinery.SourceFileLoader(modname, filename)
    module = loader.load_module()

    sys.path.remove(path)

    return module


def get_experiment(module, experiment=None):
    if experiment:
        return getattr(module, experiment)

    exps = [(k, v) for k, v in module.__dict__.items()
            if k[0] != "_" and is_experiment(v)]
    if not exps:
        raise ValueError("No experiments in module")
    if len(exps) > 1:
        raise ValueError("More than one experiment found in module")
    return exps[0][1]


def verbosity_args(parser):
    group = parser.add_argument_group("verbosity")
    group.add_argument("-v", "--verbose", default=0, action="count",
                       help="increase logging level")
    group.add_argument("-q", "--quiet", default=0, action="count",
                       help="decrease logging level")


def simple_network_args(parser, default_port):
    group = parser.add_argument_group("network server")
    group.add_argument(
        "--bind", default=[], action="append",
        help="add an hostname or IP address to bind to")
    group.add_argument(
        "--no-localhost-bind", default=False, action="store_true",
        help="do not implicitly bind to localhost addresses")
    if isinstance(default_port, int):
        group.add_argument("-p", "--port", default=default_port, type=int,
                           help="TCP port to listen to (default: %(default)d)")
    else:
        for name, purpose, default in default_port:
            h = ("TCP port to listen to for {} (default: {})"
                  .format(purpose, default))
            group.add_argument("--port-" + name, default=default, type=int,
                           help=h)

def init_logger(args):
    logging.basicConfig(level=logging.WARNING + args.quiet*10 - args.verbose*10)


def bind_address_from_args(args):
    if args.no_localhost_bind:
        return args.bind
    else:
        return ["127.0.0.1", "::1"] + args.bind


def atexit_register_coroutine(coroutine, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.run_until_complete(coroutine()))


async def exc_to_warning(coro):
    try:
        await coro
    except:
        logger.warning("asyncio coroutine terminated with exception",
                       exc_info=True)


async def asyncio_wait_or_cancel(fs, **kwargs):
    fs = [asyncio.ensure_future(f) for f in fs]
    try:
        d, p = await asyncio.wait(fs, **kwargs)
    except:
        for f in fs:
            f.cancel()
        raise
    for f in p:
        f.cancel()
        await asyncio.wait([f])
    return fs


class TaskObject:
    def start(self):
        self.task = asyncio.ensure_future(self._do())

    async def stop(self):
        self.task.cancel()
        try:
            await asyncio.wait_for(self.task, None)
        except asyncio.CancelledError:
            pass
        del self.task

    async def _do(self):
        raise NotImplementedError


class Condition:
    def __init__(self, *, loop=None):
        if loop is not None:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()
        self._waiters = collections.deque()

    async def wait(self):
        """Wait until notified."""
        fut = asyncio.Future(loop=self._loop)
        self._waiters.append(fut)
        try:
            await fut
        finally:
            self._waiters.remove(fut)

    def notify(self):
        for fut in self._waiters:
            if not fut.done():
                fut.set_result(False)


def get_windows_drives():
    from ctypes import windll

    drives = []
    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.append(letter)
        bitmask >>= 1
    return drives
