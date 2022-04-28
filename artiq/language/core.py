"""
Core ARTIQ extensions to the Python language.
"""

from typing import Generic, TypeVar
from functools import wraps
from inspect import getfullargspec, getmodule
from types import SimpleNamespace
from math import floor, ceil

from artiq.language import import_cache


__all__ = [
    "Kernel", "KernelInvariant", "virtual",
    "round64", "floor64", "ceil64",
    "extern", "kernel", "portable", "nac3", "rpc",
    "print_rpc",
    "Option", "Some", "none", "UnwrapNoneError",
    "set_time_manager",
    "parallel", "sequential",
    "delay_mu", "now_mu", "at_mu",
    "set_watchdog_factory", "watchdog", "TerminationRequested",
]


T = TypeVar('T')

class Kernel(Generic[T]):
    pass

class KernelInvariant(Generic[T]):
    pass

class virtual(Generic[T]):
    pass


def round64(x):
    return round(x)

def floor64(x):
    return floor(x)

def ceil64(x):
    return ceil(x)


_allow_registration = True
# Delay NAC3 analysis until all referenced variables are supposed to exist on the CPython side.
_registered_functions = set()
_registered_classes = set()

def _register_function(fun):
    assert _allow_registration
    import_cache.add_module_to_cache(getmodule(fun))
    _registered_functions.add(fun)

def _register_class(cls):
    assert _allow_registration
    import_cache.add_module_to_cache(getmodule(cls))
    _registered_classes.add(cls)


def extern(function):
    """Decorates a function declaration defined by the core device runtime."""
    _register_function(function)
    return function


def kernel(function_or_method):
    """Decorates a function or method to be executed on the core device."""
    _register_function(function_or_method)
    argspec = getfullargspec(function_or_method)
    if argspec.args and argspec.args[0] == "self":
        @wraps(function_or_method)
        def run_on_core(self, *args, **kwargs):
            fake_method = SimpleNamespace(__self__=self, __name__=function_or_method.__name__)
            return self.core.run(fake_method, args, kwargs)
    else:
        @wraps(function_or_method)
        def run_on_core(*args, **kwargs):
            raise RuntimeError("Kernel functions need explicit core.run()")
    run_on_core.__artiq_kernel__ = True
    return run_on_core


def portable(function):
    """Decorates a function or method to be executed on the same device (host/core device) as the caller."""
    _register_function(function)
    return function


def nac3(cls):
    """
    Decorates a class to be analyzed by NAC3.
    All classes containing kernels or portable methods must use this decorator.
    """
    _register_class(cls)
    return cls


def rpc(arg=None, flags={}):
    """
    This decorator marks a function for execution on the host interpreter.
    """
    if arg is None:
        def inner_decorator(function):
            return rpc(function, flags)
        return inner_decorator
    return arg


@rpc
def print_rpc(a: T):
    print(a)


@nac3
class UnwrapNoneError(Exception):
    """Raised when unwrapping a none Option."""
    artiq_builtin = True

class Option(Generic[T]):
    _nac3_option: T

    def __init__(self, v: T):
        self._nac3_option = v

    def is_none(self):
        return self._nac3_option is None

    def is_some(self):
        return self._nac3_option is not None

    def unwrap(self):
        if self.is_none():
            raise UnwrapNoneError()
        return self._nac3_option

    def __repr__(self) -> str:
        if self.is_none():
            return "none"
        else:
            return "Some({})".format(repr(self._nac3_option))

    def __str__(self) -> str:
        if self.is_none():
            return "none"
        else:
            return "Some({})".format(str(self._nac3_option))

def Some(v: T) -> Option[T]:
    return Option(v)

none = Option(None)


class _DummyTimeManager:
    def _not_implemented(self, *args, **kwargs):
        raise NotImplementedError(
            "Attempted to interpret kernel without a time manager")

    enter_sequential = _not_implemented
    enter_parallel = _not_implemented
    exit = _not_implemented
    take_time_mu = _not_implemented
    get_time_mu = _not_implemented
    set_time_mu = _not_implemented
    take_time = _not_implemented

_time_manager = _DummyTimeManager()

def set_time_manager(time_manager):
    """Set the time manager used for simulating kernels by running them
    directly inside the Python interpreter. The time manager responds to the
    entering and leaving of interleave/parallel/sequential blocks, delays, etc. and
    provides a time-stamped logging facility for events.
    """
    global _time_manager
    _time_manager = time_manager


@nac3
class _ParallelContextManager:
    """In a parallel block, all statements start their execution at
    the same time.
    The execution time of a parallel block is the execution time of its longest
    statement. A parallel block may contain sequential blocks, which themselves
    may contain parallel blocks, etc.
    """
    # Those methods are not actual RPCs, but they need to be registered with
    # NAC3 for the context manager to typecheck.
    # In the codegen phase, NAC3ARTIQ detects those special context managers
    # and takes over, without generating the RPC calling code.
    @rpc
    def __enter__(self):
        _time_manager.enter_parallel()

    @rpc
    def __exit__(self, *exc_info):
        _time_manager.exit()

@nac3
class _SequentialContextManager:
    """In a sequential block, statements are executed one after another, with
    the time increasing as one moves down the statement list."""
    @rpc
    def __enter__(self):
        _time_manager.enter_sequential()

    @rpc
    def __exit__(self, *exc_info):
        _time_manager.exit()

parallel = _ParallelContextManager()
sequential = _SequentialContextManager()


def delay_mu(duration):
    """Increases the RTIO time by the given amount (in machine units)."""
    _time_manager.take_time_mu(duration)


def now_mu():
    """Retrieve the current RTIO timeline cursor, in machine units.
    Note the conceptual difference between this and the current value of the
    hardware RTIO counter; see e.g.
    :meth:`artiq.coredevice.core.Core.get_rtio_counter_mu` for the latter.
    """
    return _time_manager.get_time_mu()


def at_mu(time):
    """Sets the RTIO time to the specified absolute value, in machine units."""
    _time_manager.set_time_mu(time)


class _DummyWatchdog:
    def __init__(self, timeout):
        pass

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        pass


# Watchdogs are simply not enforced by default.
_watchdog_factory = _DummyWatchdog


def set_watchdog_factory(f):
    global _watchdog_factory
    _watchdog_factory = f


def watchdog(timeout):
    return _watchdog_factory(timeout)


class TerminationRequested(Exception):
    """Raised by ``pause`` when the user has requested termination."""
    pass
