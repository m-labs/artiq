import argparse
import asyncio
import atexit
import collections
import importlib.machinery
import logging
import os
import string
import sys
from typing import Iterable, Dict, Union, NamedTuple, Sequence, Awaitable

import numpy as np

from artiq import __version__ as artiq_version
from artiq.appdirs import user_config_dir
from artiq.language.environment import is_experiment
from artiq.protocols import pyon

__all__ = ["parse_arguments", "elide", "short_format", "file_import",
           "get_experiment", "verbosity_args", "simple_network_args",
           "multiline_log_config", "init_logger", "bind_address_from_args",
           "atexit_register_coroutine", "exc_to_warning",
           "asyncio_wait_or_cancel", "TaskObject", "Condition",
           "get_windows_drives", "get_user_config_dir"]

logger = logging.getLogger(__name__)


def parse_arguments(arguments: Iterable[str]) -> Dict:
    """
    Parse arguments separated by ``=`` into a dictionary. Arguments are in format ``name=value``

    Args:
        arguments: iterable (e.g. list) of strings, containing {name, value} pairs separated by "="

    Returns:
        Dictionary mapping names to values
    """
    d = {}
    for argument in arguments:
        name, eq, value = argument.partition("=")
        d[name] = pyon.decode(value)
    return d


def elide(s: str, maxlen: int):
    """
    Cuts a string to a certain size, and adds ellipses (``...``) if the string is
    cut down.

    Args:
        s (str): string to be cut down
        maxlen: Maximum length in characters of the output string.

    Returns:
        String that has been cut to length *maxlen*. Note: ellipses count towards
        character count
    """
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
        modname = modname[i + 1:]
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


def verbosity_args(parser: argparse.ArgumentParser):
    """
    Adds verbosity (i.e. logging level) arguments to a command-line argument parser.

    Adds the ``-v/--verbose`` and ``-q/--quiet`` option, which can be repeated multiple times to increase or
    decrease default logging level (see Python standard library *Logging->Logging Levels*
    for more information).

    Using ``-v`` will increase the logging level (i.e. ERROR -> WARNING), and ``-q``
    will decrease the logging level (i.e. WARNING -> ERROR)

    Args:
        parser (argparse.ArgumentParser): command line parser to be supplemented

    Return:
        No return value. Only adds arguments to existing argument ``parser``
    """
    group = parser.add_argument_group("verbosity")
    group.add_argument("-v", "--verbose", default=0, action="count",
                       help="increase logging level")
    group.add_argument("-q", "--quiet", default=0, action="count",
                       help="decrease logging level")


NetworkPort = NamedTuple('NetworkPort', [('name', str), ('purpose', str), ('default_port', int)])


def simple_network_args(parser: argparse.ArgumentParser, default_port: Union[int, Iterable[NetworkPort]]):
    """
    Adds basic network configuration arguments to a command-line argument parser.

    This is primarily useful for command-line applications like creating network support packages,
    drivers or controllers.

    Adds the following arguments:
        * ``--bind``: additional hostname or IP addresses to bind to;
            use '*' to bind to all interfaces (default: %(default)s)"
        *

    Args:
        parser (argparse.ArgumentParser): command line parser to be supplemented
        default_port: which port the application should bind to if none is provided
            on the command-line at runtime. Should be either an ``int``, or a list of tuples
            indicating which ports to listen on. Tuples should be of form (name, purpose, default).
            Example: ``("incoming", "incoming data", 4000)``

    Return:
        No return value. Only adds arguments to existing argument ``parser``
    """
    group = parser.add_argument_group("network server")
    group.add_argument(
        "--bind", default=[], action="append",
        help="additional hostname or IP addresses to bind to; "
             "use '*' to bind to all interfaces (default: %(default)s)")
    group.add_argument(
        "--no-localhost-bind", default=False, action="store_true",
        help="do not implicitly also bind to localhost addresses")
    if isinstance(default_port, int):
        group.add_argument("-p", "--port", default=default_port, type=int,
                           help="TCP port to listen on (default: %(default)d)")
    else:
        for name, purpose, default in default_port:
            h = ("TCP port to listen on for {} connections (default: {})"
                 .format(purpose, default))
            group.add_argument("--port-" + name, default=default, type=int,
                               help=h)


class MultilineFormatter(logging.Formatter):
    """
    Logging formatter to insert number of linebreaks into the log output
    """
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


def multiline_log_config(level: int) -> None:
    """
    Creates a multiline logger (see :class:`.MultilineFormatter` for the format)

    Will default to sending data to StreamHandler(), which streams to stderr by default.

    Args:
        level: logging level to start logger with. See :func:`.init_logger` for generating this from command line,
            otherwise use default Python standard library logging levels.

    Return:
        None
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(MultilineFormatter())
    root_logger.addHandler(handler)


def init_logger(args: argparse.Namespace) -> None:
    """
    Initializes a basic logger with a logging level set by a command line parser.

    For setting up the parser, see :func:`.verbosity_args`.

    Defaults to logging WARNING and above, but level is changed by the number of ``-v/-q``
    arguments provided on command line.

    Args:
        args (argparse.Namespace): namespace containing parsed command-line arguments. Should call parser.parse_args()
            before inputting to this function.

    Returns:
        None
    """
    multiline_log_config(
        level=logging.WARNING + args.quiet * 10 - args.verbose * 10)


def bind_address_from_args(args: argparse.Namespace) -> Union[None, Sequence[str]]:
    """
    Generates network bind address(es) from parsed command-line arguments

    For setting up the parser, see :func:`.simple_network_args`.

    Depending on the input, will either return None, just the given bind arguments, or local addresses (IPv4 & IPv6) + bind arguments

    Args:
        args (argparse.Namespace): namespace containing parsed command-line arguments. Should call parser.parse_args()
            before inputting to this function.
            Should contain ``args.bind``, and ``args.no_localhost_bind`` attributes.

    Returns:
        If ``args.bind == '*'``, returns None. Otherwise, will return bind arguments.
        If ``not args.no_localhost_bind``, then adds the local IPv4/IPv6 addresses (i.e. ``127.0.0.1, ::1``)
    """
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


async def exc_to_warning(coroutine: Awaitable):
    """
    Runs a coroutine (or awaitable). If there is an exception, logs it as a warning
    and continues

    Args:
        coroutine: a coroutine or awaitable function to be run and wrapped

    Return:
        None
    """
    try:
        await coroutine
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


def get_windows_drives() -> Sequence[str]:
    """
    Returns the drive letters corresponding to drives on Windows (i.e. ``['C', 'D', ...]``)

    Returns:
        List of letters corresponding to logical (i.e. including mapped) drives on Windows
    """
    # seems to be from
    # https://stackoverflow.com/questions/827371/is-there-a-way-to-list-all-the-available-drive-letters-in-python
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
