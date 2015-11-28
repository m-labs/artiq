"""
Core ARTIQ extensions to the Python language.
"""

import os, linecache, re
from collections import namedtuple
from functools import wraps

# for runtime files in backtraces
from artiq.coredevice.runtime import source_loader


__all__ = ["host_int", "int",
           "kernel", "portable", "syscall",
           "set_time_manager", "set_watchdog_factory",
           "ARTIQException",
           "TerminationRequested"]

# global namespace for kernels
kernel_globals = (
    "sequential", "parallel",
    "delay_mu", "now_mu", "at_mu", "delay",
    "seconds_to_mu", "mu_to_seconds",
    "watchdog"
)
__all__.extend(kernel_globals)

host_int = int

class int:
    """
    Arbitrary-precision integers for static compilation.

    The static compiler does not use unlimited-precision integers,
    like Python normally does, because of their unbounded memory requirements.
    Instead, it allows to choose a bit width (usually 32 or 64) at compile-time,
    and all computations follow wrap-around semantics on overflow.

    This class implements the same semantics on the host.

    For example:

    >>> a = int(1, width=64)
    >>> b = int(3, width=64) + 2
    >>> isinstance(a, int)
    True
    >>> isinstance(b, int)
    True
    >>> a + b
    int(6, width=64)
    >>> int(10, width=32) + 0x7fffffff
    int(9, width=32)
    >>> int(0x80000000)
    int(-2147483648, width=32)
    """

    __slots__ = ['_value', '_width']

    def __new__(cls, value, width=32):
        if isinstance(value, int):
            return value
        else:
            sign_bit = 2 ** (width - 1)
            value = host_int(value)
            if value & sign_bit:
                value  = -1 & ~sign_bit + (value & (sign_bit - 1)) + 1
            else:
                value &= sign_bit - 1

            self = super().__new__(cls)
            self._value = value
            self._width = width
            return self

    @property
    def width(self):
        return self._width

    def __int__(self):
        return self._value

    def __float__(self):
        return float(self._value)

    def __str__(self):
        return str(self._value)

    # range() etc call __index__, not __int__
    def __index__(self):
        return self._value

    def __repr__(self):
        return "int({}, width={})".format(self._value, self._width)

    def _unaryop(lower_fn):
        def operator(self):
            return int(lower_fn(self._value), self._width)
        return operator

    __neg__                       = _unaryop(host_int.__neg__)
    __pos__                       = _unaryop(host_int.__pos__)
    __abs__                       = _unaryop(host_int.__abs__)
    __invert__                    = _unaryop(host_int.__invert__)
    __round__                     = _unaryop(host_int.__round__)

    def _binaryop(lower_fn, rlower_fn=None):
        def operator(self, other):
            if isinstance(other, host_int):
                return int(lower_fn(self._value, other), self._width)
            elif isinstance(other, int):
                width = self._width if self._width > other._width else other._width
                return int(lower_fn(self._value, other._value), width)
            elif rlower_fn:
                return getattr(other, rlower_fn)(self._value)
            else:
                return NotImplemented
        return operator

    __add__       = __iadd__      = _binaryop(host_int.__add__,       "__radd__")
    __sub__       = __isub__      = _binaryop(host_int.__sub__,       "__rsub__")
    __mul__       = __imul__      = _binaryop(host_int.__mul__,       "__rmul__")
    __truediv__   = __itruediv__  = _binaryop(host_int.__truediv__,   "__rtruediv__")
    __floordiv__  = __ifloordiv__ = _binaryop(host_int.__floordiv__,  "__rfloordiv__")
    __mod__       = __imod__      = _binaryop(host_int.__mod__,       "__rmod__")
    __pow__       = __ipow__      = _binaryop(host_int.__pow__,       "__rpow__")

    __radd__                      = _binaryop(host_int.__radd__,      "__add__")
    __rsub__                      = _binaryop(host_int.__rsub__,      "__sub__")
    __rmul__                      = _binaryop(host_int.__rmul__,      "__mul__")
    __rfloordiv__                 = _binaryop(host_int.__rfloordiv__, "__floordiv__")
    __rtruediv__                  = _binaryop(host_int.__rtruediv__,  "__truediv__")
    __rmod__                      = _binaryop(host_int.__rmod__,      "__mod__")
    __rpow__                      = _binaryop(host_int.__rpow__,      "__pow__")

    __lshift__    = __ilshift__   = _binaryop(host_int.__lshift__)
    __rshift__    = __irshift__   = _binaryop(host_int.__rshift__)
    __and__       = __iand__      = _binaryop(host_int.__and__)
    __or__        = __ior__       = _binaryop(host_int.__or__)
    __xor__       = __ixor__      = _binaryop(host_int.__xor__)

    __rlshift__                   = _binaryop(host_int.__rlshift__)
    __rrshift__                   = _binaryop(host_int.__rrshift__)
    __rand__                      = _binaryop(host_int.__rand__)
    __ror__                       = _binaryop(host_int.__ror__)
    __rxor__                      = _binaryop(host_int.__rxor__)

    def _compareop(lower_fn, rlower_fn):
        def operator(self, other):
            if isinstance(other, host_int):
                return lower_fn(self._value, other)
            elif isinstance(other, int):
                return lower_fn(self._value, other._value)
            else:
                return getattr(other, rlower_fn)(self._value)
        return operator

    __eq__                        = _compareop(host_int.__eq__,       "__ne__")
    __ne__                        = _compareop(host_int.__ne__,       "__eq__")
    __gt__                        = _compareop(host_int.__gt__,       "__le__")
    __ge__                        = _compareop(host_int.__ge__,       "__lt__")
    __lt__                        = _compareop(host_int.__lt__,       "__ge__")
    __le__                        = _compareop(host_int.__le__,       "__gt__")


_ARTIQEmbeddedInfo = namedtuple("_ARTIQEmbeddedInfo",
                                "core_name function syscall")

def kernel(arg):
    """
    This decorator marks an object's method for execution on the core
    device.

    When a decorated method is called from the Python interpreter, the ``core``
    attribute of the object is retrieved and used as core device driver. The
    core device driver will typically compile, transfer and run the method
    (kernel) on the device.

    When kernels call another method:
        - if the method is a kernel for the same core device, is it compiled
          and sent in the same binary. Calls between kernels happen entirely on
          the device.
        - if the method is a regular Python method (not a kernel), it generates
          a remote procedure call (RPC) for execution on the host.

    The decorator takes an optional parameter that defaults to ``core`` and
    specifies the name of the attribute to use as core device driver.
    """
    if isinstance(arg, str):
        def inner_decorator(function):
            @wraps(function)
            def run_on_core(self, *k_args, **k_kwargs):
                return getattr(self, arg).run(run_on_core, ((self,) + k_args), k_kwargs)
            run_on_core.artiq_embedded = _ARTIQEmbeddedInfo(
                core_name=arg, function=function, syscall=None)
            return run_on_core
        return inner_decorator
    else:
        return kernel("core")(arg)

def portable(function):
    """
    This decorator marks a function for execution on the same device as its
    caller.

    In other words, a decorated function called from the interpreter on the
    host will be executed on the host (no compilation and execution on the
    core device). A decorated function called from a kernel will be executed
    on the core device (no RPC).
    """
    function.artiq_embedded = \
        _ARTIQEmbeddedInfo(core_name=None, function=function, syscall=None)
    return function

def syscall(arg):
    """
    This decorator marks a function as a system call. When executed on a core
    device, a C function with the provided name (or the same name as
    the Python function, if not provided) will be called. When executed on
    host, the Python function will be called as usual.

    Every argument and the return value must be annotated with ARTIQ types.

    Only drivers should normally define syscalls.
    """
    if isinstance(arg, str):
        def inner_decorator(function):
            function.artiq_embedded = \
                _ARTIQEmbeddedInfo(core_name=None, function=None,
                                   syscall=function.__name__)
            return function
        return inner_decorator
    else:
        return syscall(arg.__name__)(arg)


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
    entering and leaving of parallel/sequential blocks, delays, etc. and
    provides a time-stamped logging facility for events.
    """
    global _time_manager
    _time_manager = time_manager


class _Sequential:
    """In a sequential block, statements are executed one after another, with
    the time increasing as one moves down the statement list."""
    def __enter__(self):
        _time_manager.enter_sequential()

    def __exit__(self, type, value, traceback):
        _time_manager.exit()
sequential = _Sequential()


class _Parallel:
    """In a parallel block, all top-level statements start their execution at
    the same time.

    The execution time of a parallel block is the execution time of its longest
    statement. A parallel block may contain sequential blocks, which themselves
    may contain parallel blocks, etc.
    """
    def __enter__(self):
        _time_manager.enter_parallel()

    def __exit__(self, type, value, traceback):
        _time_manager.exit()
parallel = _Parallel()


def delay_mu(duration):
    """Increases the RTIO time by the given amount (in machine units)."""
    _time_manager.take_time_mu(duration)


def now_mu():
    """Retrieves the current RTIO time, in machine units."""
    return _time_manager.get_time_mu()


def at_mu(time):
    """Sets the RTIO time to the specified absolute value, in machine units."""
    _time_manager.set_time_mu(time)


def delay(duration):
    """Increases the RTIO time by the given amount (in seconds)."""
    _time_manager.take_time(duration)


def seconds_to_mu(seconds, core=None):
    """Converts seconds to the corresponding number of machine units
    (RTIO cycles).

    :param seconds: time (in seconds) to convert.
    :param core: core device for which to perform the conversion. Specify only
        when running in the interpreter (not in kernel).
    """
    if core is None:
        raise ValueError("Core device must be specified for time conversion")
    return round64(seconds//core.ref_period)


def mu_to_seconds(mu, core=None):
    """Converts machine units (RTIO cycles) to seconds.

    :param mu: cycle count to convert.
    :param core: core device for which to perform the conversion. Specify only
        when running in the interpreter (not in kernel).
    """
    if core is None:
        raise ValueError("Core device must be specified for time conversion")
    return mu*core.ref_period


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


class ARTIQException(Exception):
    """Base class for exceptions raised or passed through the core device."""

    # Try and create an instance of the specific class, if one exists.
    def __new__(cls, name, message, params, traceback):
        def find_subclass(cls):
            if cls.__name__ == name:
                return cls
            else:
                for subclass in cls.__subclasses__():
                    cls = find_subclass(subclass)
                    if cls is not None:
                        return cls

        more_specific_cls = find_subclass(cls)
        if more_specific_cls is None:
            more_specific_cls = cls

        exn = Exception.__new__(more_specific_cls)
        exn.__init__(name, message, params, traceback)
        return exn

    def __init__(self, name, message, params, traceback):
        Exception.__init__(self, name, message, *params)
        self.name, self.message, self.params = name, message, params
        self.traceback = list(traceback)

    def __str__(self):
        lines = []

        if type(self).__name__ == self.name:
            lines.append(self.message.format(*self.params))
        else:
            lines.append("({}) {}".format(self.name, self.message.format(*self.params)))

        lines.append("Core Device Traceback (most recent call last):")
        for (filename, line, column, function, address) in self.traceback:
            stub_globals = {"__name__": filename, "__loader__": source_loader}
            source_line = linecache.getline(filename, line, stub_globals)
            indentation = re.search(r"^\s*", source_line).end()

            if address is None:
                formatted_address = ""
            else:
                formatted_address = " (RA=0x{:x})".format(address)

            filename = filename.replace(os.path.normpath(os.path.join(os.path.dirname(__file__),
                                                                      "..")), "<artiq>")
            if column == -1:
                lines.append("  File \"{file}\", line {line}, in {function}{address}".
                             format(file=filename, line=line, function=function,
                                    address=formatted_address))
                lines.append("    {}".format(source_line.strip() if source_line else "<unknown>"))
            else:
                lines.append("  File \"{file}\", line {line}, column {column},"
                             " in {function}{address}".
                             format(file=filename, line=line, column=column + 1,
                                    function=function, address=formatted_address))
                lines.append("    {}".format(source_line.strip() if source_line else "<unknown>"))
                lines.append("    {}^".format(" " * (column - indentation)))

        return "\n".join(lines)
