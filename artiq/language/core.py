"""
Core ARTIQ extensions to the Python language.

"""

from collections import namedtuple as _namedtuple
from copy import copy as _copy
from functools import wraps as _wraps

from artiq.language import units as _units


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


def array(element, count):
    """Creates an array.

    The array is initialized with the value of ``element`` repeated ``count``
    times. Elements can be read and written using the regular Python index
    syntax.

    For static compilation, ``count`` must be a fixed integer.

    Arrays of arrays are supported.

    """
    return [_copy(element) for i in range(count)]


class AutoContext:
    """Base class to automate device and parameter discovery.

    Drivers and experiments should in most cases overload this class to
    obtain the parameters and devices (including the core device) that they
    need.

    This class sets all its ``__init__`` keyword arguments as attributes. It
    then iterates over each element in its ``parameters`` attribute and, if
    they are not already existing, requests them from ``mvs`` (Missing Value
    Supplier).

    A ``AutoContext`` instance can be used as MVS. If the requested parameter
    is within its attributes, the value of that attribute is returned.
    Otherwise, the request is forwarded to the parent MVS.

    All keyword arguments are set as object attributes. This enables setting
    parameters of a lower-level ``AutoContext`` object using keyword arguments
    without having those explicitly listed in the upper-level ``AutoContext``
    parameter list.

    At the top-level, it is possible to have a MVS that issues requests to a
    database and hardware management system.

    :var parameters: A string containing the parameters that the object must
        have. It must be a space-separated list of valid Python identifiers.
        Default: empty.
    :var implicit_core: Automatically adds ``core`` to the parameter list.
        Default: True.

    Example:

    >>> class SubExperiment(AutoContext):
    ...     parameters = "foo bar"
    ...
    ...     def run():
    ...         do_something(self.foo, self.bar)
    ...
    >>> class MainExperiment(AutoContext):
    ...     parameters = "bar1 bar2 offset"
    ...
    ...     def build(self):
    ...         self.exp1 = SubExperiment(self, bar=self.bar1)
    ...         self.exp2 = SubExperiment(self, bar=self.bar2)
    ...         self.exp3 = SubExperiment(self, bar=self.bar2 + self.offset)
    ...
    ...     def run():
    ...         self.exp1.run()
    ...         self.exp2.run()
    ...         self.exp3.run()
    ...
    >>> # does not require a database.
    >>> a = MainExperiment(foo=1, bar1=2, bar2=3, offset=0)
    >>> # "foo" and "offset" are automatically retrieved from the database.
    >>> b = MainExperiment(db_mvs, bar1=2, bar2=3)

    """
    parameters = ""
    implicit_core = True

    def __init__(self, mvs=None, **kwargs):
        self.mvs = mvs
        for k, v in kwargs.items():
            setattr(self, k, v)

        parameters = self.parameters.split()
        if self.implicit_core:
            parameters.append("core")
        for parameter in parameters:
            try:
                value = getattr(self, parameter)
            except AttributeError:
                value = self.mvs.get_missing_value(parameter)
                setattr(self, parameter, value)

        self.build()

    def get_missing_value(self, parameter):
        """Attempts to retrieve ``parameter`` from the object's attributes.
        If not present, forwards the request to the parent MVS.

        The presence of this method makes ``AutoContext`` act as a MVS.
        """
        try:
            return getattr(self, parameter)
        except AttributeError:
            return self.mvs.get_missing_value(parameter)

    def build(self):
        """This is called by ``__init__`` after the parameter initialization
        is done.

        The user may overload this method to complete the object's
        initialization with all parameters available.

        """
        pass


_KernelFunctionInfo = _namedtuple("_KernelFunctionInfo", "core_name k_function")


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
            @_wraps(k_function)
            def run_on_core(exp, *k_args, **k_kwargs):
                getattr(exp, arg).run(k_function, ((exp,) + k_args), k_kwargs)
            run_on_core.k_function_info = _KernelFunctionInfo(
                core_name=arg, k_function=k_function)
            return run_on_core
        return real_decorator
    else:
        @_wraps(arg)
        def run_on_core(exp, *k_args, **k_kwargs):
            exp.core.run(arg, ((exp,) + k_args), k_kwargs)
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
    take_time = _not_implemented
    get_time = _not_implemented
    set_time = _not_implemented

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

# global namespace for kernels

kernel_globals = ("sequential", "parallel",
    "delay", "now", "at", "time_to_cycles", "cycles_to_time",
    "syscall")


class _Sequential:
    """In a sequential block, statements are executed one after another, with
    the time increasing as one moves down the statement list.

    """
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


def delay(duration):
    """Increases the RTIO time by the given amount.

    """
    _time_manager.take_time(duration)


def now():
    """Retrieves the current RTIO time, in seconds.

    """
    return _time_manager.get_time()


def at(time):
    """Sets the RTIO time to the specified absolute value.

    """
    _time_manager.set_time(time)


def time_to_cycles(time, core=None):
    """Converts time to the corresponding number of RTIO cycles.

    :param time: Time (in seconds) to convert.
    :param core: Core device for which to perform the conversion. Specify only
        when running in the interpreter (not in kernel).

    """
    if core is None:
        raise ValueError("Core device must be specified for time conversion")
    return round64(time.amount//core.runtime_env.ref_period)


def cycles_to_time(cycles, core=None):
    """Converts RTIO cycles to the corresponding time.

    :param time: Cycle count to convert.
    :param core: Core device for which to perform the conversion. Specify only
        when running in the interpreter (not in kernel).

    """
    if core is None:
        raise ValueError("Core device must be specified for time conversion")
    return cycles*core.runtime_env.ref_period*_units.s


def syscall(*args):
    """Invokes a service of the runtime.

    Kernels use this function to interface to the outside world: program RTIO
    events, make RPCs, etc.

    Only drivers should normally use ``syscall``.

    """
    return _syscall_manager.do(*args)


_encoded_exceptions = dict()


def EncodedException(eid):
    """Represents exceptions on the core device, which are identified
    by a single number.

    """
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
    pass


first_user_eid = 1024
