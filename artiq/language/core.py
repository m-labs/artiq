"""
Core ARTIQ extensions to the Python language.
"""

from collections import namedtuple
from functools import wraps


__all__ = ["int64", "round64", "kernel", "portable",
           "set_time_manager", "set_syscall_manager", "set_watchdog_factory",
           "RuntimeException", "EncodedException"]

# global namespace for kernels
kernel_globals = ("sequential", "parallel",
    "delay_mu", "now_mu", "at_mu", "delay",
    "seconds_to_mu", "mu_to_seconds",
    "syscall", "watchdog")
__all__.extend(kernel_globals)


class int64(int):
    """64-bit integers for static compilation.

    When this class is used instead of Python's ``int``, the static compiler
    stores the corresponding variable on 64 bits instead of 32.

    When used in the interpreter, it behaves as ``int`` and the results of
    integer operations involving it are also ``int64`` (which matches the
    size promotion rules of the static compiler). This way, it is possible to
    specify 64-bit size annotations on constants that are passed to the
    kernels.

    Example:

    >>> a = int64(1)
    >>> b = int64(3) + 2
    >>> isinstance(a, int64)
    True
    >>> isinstance(b, int64)
    True
    >>> a + b
    6
    """
    pass

def _make_int64_op_method(int_method):
    def method(self, *args):
        r = int_method(self, *args)
        if isinstance(r, int):
            r = int64(r)
        return r
    return method

for _op_name in ("neg", "pos", "abs", "invert", "round",
                 "add", "radd", "sub", "rsub", "mul", "rmul", "pow", "rpow",
                 "lshift", "rlshift", "rshift", "rrshift",
                 "and", "rand", "xor", "rxor", "or", "ror",
                 "floordiv", "rfloordiv", "mod", "rmod"):
    _method_name = "__" + _op_name + "__"
    _orig_method = getattr(int, _method_name)
    setattr(int64, _method_name, _make_int64_op_method(_orig_method))

for _op_name in ("add", "sub", "mul", "floordiv", "mod",
                 "pow", "lshift", "rshift", "lshift",
                 "and", "xor", "or"):
    _op_method = getattr(int, "__" + _op_name + "__")
    setattr(int64, "__i" + _op_name + "__", _make_int64_op_method(_op_method))


def round64(x):
    """Rounds to a 64-bit integer.

    This function is equivalent to ``int64(round(x))`` but, when targeting
    static compilation, prevents overflow when the rounded value is too large
    to fit in a 32-bit integer.
    """
    return int64(round(x))


_KernelFunctionInfo = namedtuple("_KernelFunctionInfo", "core_name k_function")


def kernel(arg):
    """This decorator marks an object's method for execution on the core
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
        def real_decorator(k_function):
            @wraps(k_function)
            def run_on_core(exp, *k_args, **k_kwargs):
                return getattr(exp, arg).run(k_function,
                                             ((exp,) + k_args), k_kwargs)
            run_on_core.k_function_info = _KernelFunctionInfo(
                core_name=arg, k_function=k_function)
            return run_on_core
        return real_decorator
    else:
        @wraps(arg)
        def run_on_core(exp, *k_args, **k_kwargs):
            return exp.core.run(arg, ((exp,) + k_args), k_kwargs)
        run_on_core.k_function_info = _KernelFunctionInfo(
            core_name="core", k_function=arg)
        return run_on_core


def portable(f):
    """This decorator marks a function for execution on the same device as its
    caller.

    In other words, a decorated function called from the interpreter on the
    host will be executed on the host (no compilation and execution on the
    core device). A decorated function called from a kernel will be executed
    on the core device (no RPC).
    """
    f.k_function_info = _KernelFunctionInfo(core_name="", k_function=f)
    return f


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


class _DummySyscallManager:
    def do(self, *args):
        raise NotImplementedError(
            "Attempted to interpret kernel without a syscall manager")

_syscall_manager = _DummySyscallManager()


def set_syscall_manager(syscall_manager):
    """Set the system call manager used for simulating the core device's
    runtime in the Python interpreter.
    """
    global _syscall_manager
    _syscall_manager = syscall_manager


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


def syscall(*args):
    """Invokes a service of the runtime.

    Kernels use this function to interface to the outside world: program RTIO
    events, make RPCs, etc.

    Only drivers should normally use ``syscall``.
    """
    return _syscall_manager.do(*args)


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


_encoded_exceptions = dict()


def EncodedException(eid):
    """Represents exceptions on the core device, which are identified
    by a single number."""
    try:
        return _encoded_exceptions[eid]
    except KeyError:
        class EncodedException(Exception):
            def __init__(self):
                Exception.__init__(self, eid)
        _encoded_exceptions[eid] = EncodedException
        return EncodedException


class RuntimeException(Exception):
    """Base class for all exceptions used by the device runtime.
    Those exceptions are defined in ``artiq.coredevice.runtime_exceptions``.
    """
    def __init__(self, core, p0, p1, p2):
        Exception.__init__(self)
        self.core = core
        self.p0 = p0
        self.p1 = p1
        self.p2 = p2


first_user_eid = 1024
