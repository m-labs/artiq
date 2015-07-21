from operator import itemgetter
import importlib.machinery
import linecache
import logging
import sys
import asyncio
import time
import os.path

from artiq.language.environment import is_experiment
from artiq.protocols import pyon


def parse_arguments(arguments):
    d = {}
    for argument in arguments:
        name, eq, value = argument.partition("=")
        d[name] = pyon.decode(value)
    return d


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


def get_experiment(module, experiment=None):
    if experiment:
        return getattr(module, experiment)

    exps = [(k, v) for k, v in module.__dict__.items()
            if is_experiment(v)]
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
    group = parser.add_argument_group("network")
    group.add_argument("--bind", default="::1",
                       help="hostname or IP address to bind to")
    group.add_argument("-p", "--port", default=default_port, type=int,
                       help="TCP port to listen to (default: %(default)d)")


def init_logger(args):
    logging.basicConfig(level=logging.WARNING + args.quiet*10 - args.verbose*10)


@asyncio.coroutine
def asyncio_process_wait_timeout(process, timeout):
    # In Python < 3.5, asyncio.wait_for(process.wait(), ...
    # causes a futures.InvalidStateError inside asyncio if and when the
    # process terminates after the timeout.
    # Work around this problem.
    @asyncio.coroutine
    def process_wait_returncode_timeout():
        while True:
            if process.returncode is not None:
                break
            yield from asyncio.sleep(0.1)
    yield from asyncio.wait_for(process_wait_returncode_timeout(),
                                timeout=timeout)

@asyncio.coroutine
def asyncio_process_wait(process):
    r = True
    while r:
        f, p = yield from asyncio.wait([process.stdout.read(1024)])
        r = f.pop().result()


@asyncio.coroutine
def asyncio_wait_or_cancel(fs, **kwargs):
    fs = [asyncio.async(f) for f in fs]
    try:
        d, p = yield from asyncio.wait(fs, **kwargs)
    except:
        for f in fs:
            f.cancel()
        raise
    for f in p:
        f.cancel()
        yield from asyncio.wait([f])
    return fs


def asyncio_queue_peek(q):
    """Like q.get_nowait(), but does not remove the item from the queue."""
    if q._queue:
        return q._queue[0]
    else:
        raise asyncio.QueueEmpty


class TaskObject:
    def start(self):
        self.task = asyncio.async(self._do())

    @asyncio.coroutine
    def stop(self):
        self.task.cancel()
        yield from asyncio.wait([self.task])
        del self.task

    @asyncio.coroutine
    def _do(self):
        raise NotImplementedError


class WaitSet:
    def __init__(self):
        self._s = set()
        self._ev = asyncio.Event()

    def _update_ev(self):
        if self._s:
            self._ev.clear()
        else:
            self._ev.set()

    def add(self, e):
        self._s.add(e)
        self._update_ev()

    def discard(self, e):
        self._s.discard(e)
        self._update_ev()

    @asyncio.coroutine
    def wait_empty(self):
        yield from self._ev.wait()
