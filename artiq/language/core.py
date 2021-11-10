"""
Core ARTIQ extensions to the Python language.
"""

from typing import Generic, TypeVar
from functools import wraps
from inspect import getfullargspec, getmodule
from types import SimpleNamespace


__all__ = [
    "KernelInvariant", "round64",
    "extern", "kernel", "portable", "nac3", "rpc",
    "parallel", "sequential",
    "set_watchdog_factory", "watchdog", "TerminationRequested"
]


T = TypeVar('T')
class KernelInvariant(Generic[T]):
    pass


def round64(x):
    return round(x)


_allow_module_registration = True
_registered_modules = set()

def _register_module_of(obj):
    assert _allow_module_registration
    # Delay NAC3 analysis until all referenced variables are supposed to exist on the CPython side.
    _registered_modules.add(getmodule(obj))


def extern(function):
    """Decorates a function declaration defined by the core device runtime."""
    _register_module_of(function)
    return function


def kernel(function_or_method):
    """Decorates a function or method to be executed on the core device."""
    _register_module_of(function_or_method)
    argspec = getfullargspec(function_or_method)
    if argspec.args and argspec.args[0] == "self":
        @wraps(function_or_method)
        def run_on_core(self, *args, **kwargs):
            fake_method = SimpleNamespace(__self__=self, __name__=function_or_method.__name__)
            self.core.run(fake_method, *args, **kwargs)
    else:
        @wraps(function_or_method)
        def run_on_core(*args, **kwargs):
            raise RuntimeError("Kernel functions need explicit core.run()")
    run_on_core.__artiq_kernel__ = True
    return run_on_core


def portable(function):
    """Decorates a function or method to be executed on the same device (host/core device) as the caller."""
    _register_module_of(function)
    return function


def nac3(cls):
    """
    Decorates a class to be analyzed by NAC3.
    All classes containing kernels or portable methods must use this decorator.
    """
    _register_module_of(cls)
    return cls


def rpc(arg=None, flags={}):
    """
    This decorator marks a function for execution on the host interpreter.
    """
    if arg is None:
        def inner_decorator(function):
            return rpc(function, flags)
        return inner_decorator


@nac3
class KernelContextManager:
    @kernel
    def __enter__(self):
        pass

    @kernel
    def __exit__(self):
        pass

parallel = KernelContextManager()
sequential = KernelContextManager()



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
