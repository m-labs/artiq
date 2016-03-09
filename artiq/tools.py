from operator import itemgetter
import importlib.machinery
import linecache
import logging
import sys
import asyncio
import time
import collections
import os
import socket
import itertools
import atexit
import string

import numpy as np

from artiq.language.environment import is_experiment
from artiq.protocols import pyon


__all__ = ["parse_arguments", "elide", "short_format", "file_import",
           "get_experiment", "verbosity_args", "simple_network_args", "init_logger",
           "bind_address_from_args", "atexit_register_coroutine",
           "exc_to_warning", "asyncio_wait_or_cancel",
           "TaskObject", "Condition", "get_windows_drives"]


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
    multiline_log_config(level=logging.WARNING + args.quiet*10 - args.verbose*10)


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

if sys.version_info[:3] == (3, 5, 1):
    # See https://github.com/m-labs/artiq/issues/253
    @asyncio.coroutines.coroutine
    def create_server(self, protocol_factory, host=None, port=None,
                      *,
                      family=socket.AF_UNSPEC,
                      flags=socket.AI_PASSIVE,
                      sock=None,
                      backlog=100,
                      ssl=None,
                      reuse_address=None,
                      reuse_port=None):
        """Create a TCP server.
        The host parameter can be a string, in that case the TCP server is bound
        to host and port.
        The host parameter can also be a sequence of strings and in that case
        the TCP server is bound to all hosts of the sequence. If a host
        appears multiple times (possibly indirectly e.g. when hostnames
        resolve to the same IP address), the server is only bound once to that
        host.
        Return a Server object which can be used to stop the service.
        This method is a coroutine.
        """
        if isinstance(ssl, bool):
            raise TypeError('ssl argument must be an SSLContext or None')
        if host is not None or port is not None:
            if sock is not None:
                raise ValueError(
                    'host/port and sock can not be specified at the same time')

            AF_INET6 = getattr(socket, 'AF_INET6', 0)
            if reuse_address is None:
                reuse_address = os.name == 'posix' and sys.platform != 'cygwin'
            sockets = []
            if host == '':
                hosts = [None]
            elif (isinstance(host, str) or
                  not isinstance(host, collections.Iterable)):
                hosts = [host]
            else:
                hosts = host

            fs = [self._create_server_getaddrinfo(host, port, family=family,
                                                  flags=flags)
                  for host in hosts]
            infos = yield from asyncio.tasks.gather(*fs, loop=self)
            infos = set(itertools.chain.from_iterable(infos))

            completed = False
            try:
                for res in infos:
                    af, socktype, proto, canonname, sa = res
                    try:
                        sock = socket.socket(af, socktype, proto)
                    except socket.error:
                        # Assume it's a bad family/type/protocol combination.
                        if self._debug:
                            asyncio.log.logger.warning('create_server() failed to create '
                                           'socket.socket(%r, %r, %r)',
                                           af, socktype, proto, exc_info=True)
                        continue
                    sockets.append(sock)
                    if reuse_address:
                        sock.setsockopt(
                            socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
                    if reuse_port:
                        if not hasattr(socket, 'SO_REUSEPORT'):
                            raise ValueError(
                                'reuse_port not supported by socket module')
                        else:
                            sock.setsockopt(
                                socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
                    # Disable IPv4/IPv6 dual stack support (enabled by
                    # default on Linux) which makes a single socket
                    # listen on both address families.
                    if af == AF_INET6 and hasattr(socket, 'IPPROTO_IPV6'):
                        sock.setsockopt(socket.IPPROTO_IPV6,
                                        socket.IPV6_V6ONLY,
                                        True)
                    try:
                        sock.bind(sa)
                    except OSError as err:
                        raise OSError(err.errno, 'error while attempting '
                                      'to bind on address %r: %s'
                                      % (sa, err.strerror.lower()))
                completed = True
            finally:
                if not completed:
                    for sock in sockets:
                        sock.close()
        else:
            if sock is None:
                raise ValueError('Neither host/port nor sock were specified')
            sockets = [sock]

        server = asyncio.base_events.Server(self, sockets)
        for sock in sockets:
            sock.listen(backlog)
            sock.setblocking(False)
            self._start_serving(protocol_factory, sock, ssl, server)
        if self._debug:
            asyncio.log.logger.info("%r is serving", server)
        return server

    asyncio.base_events.BaseEventLoop.create_server = create_server
