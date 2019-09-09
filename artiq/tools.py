import asyncio
import atexit
import collections
import contextlib
import importlib.machinery
import logging
import os
import string
import sys

import numpy as np

from artiq import __version__ as artiq_version
from artiq.appdirs import user_config_dir
from artiq.language.environment import is_experiment
from artiq.protocols import pyon

__all__ = ["parse_arguments", "elide", "short_format", "file_import",
           "get_experiment", "add_common_args", "simple_network_args",
           "UnexpectedLogMessageError", "expect_no_log_messages",
           "multiline_log_config", "init_logger", "bind_address_from_args",
           "atexit_register_coroutine", "exc_to_warning",
           "asyncio_wait_or_cancel", "TaskObject", "Condition",
           "get_windows_drives", "get_user_config_dir"]


logger = logging.getLogger(__name__)


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
    if np.issubdtype(t, np.number) or np.issubdtype(t, np.bool_):
        return str(v)
    elif np.issubdtype(t, np.unicode_):
        return "\"" + elide(v, 50) + "\""
    else:
        r = t.__name__
        if t is list or t is dict or t is set:
            r += " ({})".format(len(v))
        if t is np.ndarray:
            r += " " + str(np.shape(v))
        return r


def file_import(filename, prefix="file_import_"):
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
    try:
        loader = importlib.machinery.SourceFileLoader(modname, filename)
        module = loader.load_module()
    finally:
        sys.path.remove(path)

    return module


def get_experiment(module, class_name=None):
    if class_name:
        return getattr(module, class_name)

    exps = [(k, v) for k, v in module.__dict__.items()
            if k[0] != "_" and is_experiment(v)]
    if not exps:
        raise ValueError("No experiments in module")
    if len(exps) > 1:
        raise ValueError("More than one experiment found in module")
    return exps[0][1]


def add_common_args(parser):
    """Add common utility arguments to the cmd parser.
    
    Arguments added:
        * `-v`/`-q`: increase or decrease the default logging levels. 
            Repeat for higher levels.
        * `--version`: print the ARTIQ version
    """
    group = parser.add_argument_group("common")
    group.add_argument("-v", "--verbose", default=0, action="count",
                       help="increase logging level")
    group.add_argument("-q", "--quiet", default=0, action="count",
                       help="decrease logging level")
    group.add_argument("--version", action="version",
                       version="ARTIQ v{}".format(artiq_version),
                       help="print the ARTIQ version number")


def simple_network_args(parser, default_port):
    group = parser.add_argument_group("network server")
    group.add_argument(
        "--bind", default=[], action="append",
        help="additional hostname or IP address to bind to; "
        "use '*' to bind to all interfaces (default: %(default)s)")
    group.add_argument(
        "--no-localhost-bind", default=False, action="store_true",
        help="do not implicitly also bind to localhost addresses")
    if isinstance(default_port, int):
        group.add_argument("-p", "--port", default=default_port, type=int,
                           help="TCP port to listen on (default: %(default)d)")
    else:
        for name, purpose, default in default_port:
            h = ("TCP port for {} connections (default: {})"
                 .format(purpose, default))
            group.add_argument("--port-" + name, default=default, type=int,
                               help=h)


class UnexpectedLogMessageError(Exception):
    pass


class FailingLogHandler(logging.Handler):
    def emit(self, record):
        raise UnexpectedLogMessageError("Unexpected log message: '{}'".format(
            record.getMessage()))


@contextlib.contextmanager
def expect_no_log_messages(level, logger=None):
    """Raise an UnexpectedLogMessageError if a log message of the given level
    (or above) is emitted while the context is active.

    Example: ::

        with expect_no_log_messages(logging.ERROR):
            do_stuff_that_should_not_log_errors()
    """
    if logger is None:
        logger = logging.getLogger()
    handler = FailingLogHandler(level)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)


class MultilineFormatter(logging.Formatter):
    def __init__(self):
        logging.Formatter.__init__(
            self, "%(levelname)s:%(name)s:%(message)s")

    def format(self, record):
        r = logging.Formatter.format(self, record)
        linebreaks = r.count("\n")
        if linebreaks:
            i = r.index(":")
            r = r[:i] + "<" + str(linebreaks + 1) + ">" + r[i:]
        return r


def multiline_log_config(level):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(MultilineFormatter())
    root_logger.addHandler(handler)


def init_logger(args):
    multiline_log_config(
        level=logging.WARNING + args.quiet*10 - args.verbose*10)


def bind_address_from_args(args):
    if "*" in args.bind:
        return None
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
        async def log_exceptions(awaitable):
            try:
                return await awaitable()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("Unhandled exception in TaskObject task body", exc_info=True)
                raise

        self.task = asyncio.ensure_future(log_exceptions(self._do))

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


def get_user_config_dir():
    major = artiq_version.split(".")[0]
    dir = user_config_dir("artiq", "m-labs", major)
    os.makedirs(dir, exist_ok=True)
    return dir
