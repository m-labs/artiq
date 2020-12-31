"""
Core ARTIQ extensions to the Python language.
"""

from collections import namedtuple
from functools import wraps
import numpy


__all__ = ["kernel", "portable", "rpc", "syscall", "host_only",
           "kernel_from_string", "set_time_manager", "set_watchdog_factory",
           "TerminationRequested"]

# global namespace for kernels
kernel_globals = (
    "sequential", "parallel", "interleave",
    "delay_mu", "now_mu", "at_mu", "delay",
    "watchdog"
)
__all__.extend(kernel_globals)


_ARTIQEmbeddedInfo = namedtuple("_ARTIQEmbeddedInfo",
                                "core_name portable function syscall forbidden flags")

def kernel(arg=None, flags={}):
    """
    This decorator marks an object's method for execution on the core
    device.

    When a decorated method is called from the Python interpreter, the :attr:`core`
    attribute of the object is retrieved and used as core device driver. The
    core device driver will typically compile, transfer and run the method
    (kernel) on the device.

    When kernels call another method:

        - if the method is a kernel for the same core device, it is compiled
          and sent in the same binary. Calls between kernels happen entirely on
          the device.
        - if the method is a regular Python method (not a kernel), it generates
          a remote procedure call (RPC) for execution on the host.

    The decorator takes an optional parameter that defaults to :attr`core` and
    specifies the name of the attribute to use as core device driver.

    This decorator must be present in the global namespace of all modules using
    it for the import cache to work properly.
    """
    if isinstance(arg, str):
        def inner_decorator(function):
            @wraps(function)
            def run_on_core(self, *k_args, **k_kwargs):
                return getattr(self, arg).run(run_on_core, ((self,) + k_args), k_kwargs)
            run_on_core.artiq_embedded = _ARTIQEmbeddedInfo(
                core_name=arg, portable=False, function=function, syscall=None,
                forbidden=False, flags=set(flags))
            return run_on_core
        return inner_decorator
    elif arg is None:
        def inner_decorator(function):
            return kernel(function, flags)
        return inner_decorator
    else:
        return kernel("core", flags)(arg)

def portable(arg=None, flags={}):
    """
    This decorator marks a function for execution on the same device as its
    caller.

    In other words, a decorated function called from the interpreter on the
    host will be executed on the host (no compilation and execution on the
    core device). A decorated function called from a kernel will be executed
    on the core device (no RPC).

    This decorator must be present in the global namespace of all modules using
    it for the import cache to work properly.
    """
    if arg is None:
        def inner_decorator(function):
            return portable(function, flags)
        return inner_decorator
    else:
        arg.artiq_embedded = \
            _ARTIQEmbeddedInfo(core_name=None, portable=True, function=arg, syscall=None,
                               forbidden=False, flags=set(flags))
        return arg

def rpc(arg=None, flags={}):
    """
    This decorator marks a function for execution on the host interpreter.
    This is also the default behavior of ARTIQ; however, this decorator allows
    specifying additional flags.
    """
    if arg is None:
        def inner_decorator(function):
            return rpc(function, flags)
        return inner_decorator
    else:
        arg.artiq_embedded = \
            _ARTIQEmbeddedInfo(core_name=None, portable=False, function=arg, syscall=None,
                               forbidden=False, flags=set(flags))
        return arg

def syscall(arg=None, flags={}):
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
                _ARTIQEmbeddedInfo(core_name=None, portable=False, function=None,
                                   syscall=arg, forbidden=False,
                                   flags=set(flags))
            return function
        return inner_decorator
    elif arg is None:
        def inner_decorator(function):
            return syscall(function.__name__, flags)(function)
        return inner_decorator
    else:
        return syscall(arg.__name__)(arg)

def host_only(function):
    """
    This decorator marks a function so that it can only be executed
    in the host Python interpreter.
    """
    function.artiq_embedded = \
        _ARTIQEmbeddedInfo(core_name=None, portable=False, function=None, syscall=None,
                           forbidden=True, flags={})
    return function


def kernel_from_string(parameters, body_code, decorator=kernel):
    """Build a kernel function from the supplied source code in string form,
    similar to ``exec()``/``eval()``.

    Operating on pieces of source code as strings is a very brittle form of
    metaprogramming; kernels generated like this are hard to debug, and
    inconvenient to write. Nevertheless, this can sometimes be useful to work
    around restrictions in ARTIQ Python. In that instance, care should be taken
    to keep string-generated code to a minimum and cleanly separate it from
    surrounding code.

    The resulting function declaration is also evaluated using ``exec()`` for
    use from host Python code. To encourage a modicum of code hygiene, no
    global symbols are available by default; any objects accessed by the
    function body must be passed in explicitly as parameters.

    :param parameters: A list of parameter names the generated functions
        accepts. Each entry can either be a string or a tuple of two strings;
        if the latter, the second element specifies the type annotation.
    :param body_code: The code for the function body, in string form.
        ``return`` statements can be used to return values, as usual.
    :param decorator: One of ``kernel`` or ``portable`` (optionally with
        parameters) to specify how the function will be executed.

    :return: The function generated from the arguments.
    """

    # Build complete function declaration.
    decl = "def kernel_from_string_fn("
    for p in parameters:
        type_annotation = ""
        if isinstance(p, tuple):
            name, typ = p
            type_annotation = ": " + typ
        else:
            name = p
        decl += name + type_annotation + ","
    decl += "):\n"
    decl += "\n".join("    " + line for line in body_code.split("\n"))

    # Evaluate to get host-side function declaration.
    context = {}
    try:
        exec(decl, context)
    except SyntaxError:
        raise SyntaxError("Error parsing kernel function: '{}'".format(decl))
    fn = decorator(context["kernel_from_string_fn"])

    # Save source code for the compiler to pick up later.
    fn.artiq_embedded = fn.artiq_embedded._replace(function=decl)
    return fn


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
    may contain interleave blocks, etc.
    """
    def __enter__(self):
        _time_manager.enter_parallel()

    def __exit__(self, type, value, traceback):
        _time_manager.exit()
parallel = _Parallel()
interleave = _Parallel() # no difference in semantics on host

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


def delay(duration):
    """Increases the RTIO time by the given amount (in seconds)."""
    _time_manager.take_time(duration)


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
