from collections import OrderedDict
from inspect import isclass


__all__ = ["NoDefault",
           "FreeValue", "BooleanValue", "EnumerationValue",
           "NumberValue", "StringValue",
           "HasEnvironment",
           "Experiment", "EnvExperiment", "is_experiment"]


class NoDefault:
    """Represents the absence of a default value."""
    pass


class DefaultMissing(Exception):
    """Raised by the ``default`` method of argument processors when no default
    value is available."""
    pass


class _SimpleArgProcessor:
    def __init__(self, default=NoDefault):
        if default is not NoDefault:
            self.default_value = default

    def default(self):
        if not hasattr(self, "default_value"):
            raise DefaultMissing
        return self.default_value

    def process(self, x):
        return x

    def describe(self):
        d = {"ty": self.__class__.__name__}
        if hasattr(self, "default_value"):
            d["default"] = self.default_value
        return d


class FreeValue(_SimpleArgProcessor):
    """An argument that can be an arbitrary Python value."""
    pass


class BooleanValue(_SimpleArgProcessor):
    """A boolean argument."""
    pass


class EnumerationValue(_SimpleArgProcessor):
    """An argument that can take a string value among a predefined set of
    values.

    :param choices: A list of string representing the possible values of the
        argument.
    """
    def __init__(self, choices, default=NoDefault):
        _SimpleArgProcessor.__init__(self, default)
        assert default is NoDefault or default in choices
        self.choices = choices

    def describe(self):
        d = _SimpleArgProcessor.describe(self)
        d["choices"] = self.choices
        return d


class NumberValue(_SimpleArgProcessor):
    """An argument that can take a numerical value (typically floating point).

    :param unit: A string representing the unit of the value, for user
        interface (UI) purposes.
    :param step: The step with with the value should be modified by up/down
        buttons in a UI.
    :param min: The minimum value of the argument.
    :param max: The maximum value of the argument.
    """
    def __init__(self, default=NoDefault, unit="", step=None,
                 min=None, max=None):
        _SimpleArgProcessor.__init__(self, default)
        self.unit = unit
        self.step = step
        self.min = min
        self.max = max

    def describe(self):
        d = _SimpleArgProcessor.describe(self)
        d["unit"] = self.unit
        d["step"] = self.step
        d["min"] = self.min
        d["max"] = self.max
        return d


class StringValue(_SimpleArgProcessor):
    """A string argument."""
    pass


class HasEnvironment:
    """Provides methods to manage the environment of an experiment (devices,
    parameters, results, arguments)."""
    def __init__(self, dmgr=None, pdb=None, rdb=None, *,
                 param_override=dict(), default_arg_none=False, **kwargs):
        self.requested_args = OrderedDict()

        self.__dmgr = dmgr
        self.__pdb = pdb
        self.__rdb = rdb
        self.__param_override = param_override
        self.__default_arg_none = default_arg_none

        self.__kwargs = kwargs
        self.__in_build = True
        self.build()
        self.__in_build = False
        for key in self.__kwargs.keys():
            if key not in self.requested_args:
                raise TypeError("Got unexpected argument: " + key)
        del self.__kwargs

    def build(self):
        """Must be implemented by the user to request arguments.

        Other initialization steps such as requesting devices and parameters
        or initializing real-time results may also be performed here.

        When the repository is scanned, any requested devices and parameters
        are set to ``None``."""
        raise NotImplementedError

    def dbs(self):
        return self.__dmgr, self.__pdb, self.__rdb

    def get_argument(self, key, processor=None):
        """Retrieves and returns the value of an argument.

        :param key: Name of the argument.
        :param processor: A description of how to process the argument, such
            as instances of ``BooleanValue`` and ``NumberValue``.
        """
        if not self.__in_build:
            raise TypeError("get_argument() should only "
                            "be called from build()")
        if processor is None:
            processor = FreeValue()
        self.requested_args[key] = processor
        try:
            argval = self.__kwargs[key]
        except KeyError:
            try:
                return processor.default()
            except DefaultMissing:
                if self.__default_arg_none:
                    return None
                else:
                    raise
        return processor.process(argval)

    def attr_argument(self, key, processor=None):
        """Sets an argument as attribute. The names of the argument and of the
        attribute are the same."""
        setattr(self, key, self.get_argument(key, processor))

    def get_device(self, key):
        """Creates and returns a device driver."""
        if self.__dmgr is None:
            raise ValueError("Device manager not present")
        return self.__dmgr.get(key)

    def attr_device(self, key):
        """Sets a device driver as attribute. The names of the device driver
         and of the attribute are the same."""
        setattr(self, key, self.get_device(key))

    def get_parameter(self, key, default=NoDefault):
        """Retrieves and returns a parameter."""
        if self.__pdb is None:
            raise ValueError("Parameter database not present")
        if key in self.__param_override:
            return self.__param_override[key]
        try:
            return self.__pdb.get(key)
        except KeyError:
            if default is not NoDefault:
                return default
            else:
                raise

    def attr_parameter(self, key, default=NoDefault):
        """Sets a parameter as attribute. The names of the argument and of the
        parameter are the same."""
        setattr(self, key, self.get_parameter(key, default))

    def set_parameter(self, key, value):
        """Writes the value of a parameter into the parameter database."""
        if self.__pdb is None:
            raise ValueError("Parameter database not present")
        self.__pdb.set(key, value)

    def set_result(self, key, value, realtime=False):
        """Writes the value of a result.

        :param realtime: Marks the result as real-time, making it immediately
            available to clients such as the user interface. Returns a
            ``Notifier`` instance that can be used to modify mutable results
            (such as lists) and synchronize the modifications with the clients.
        """
        if self.__rdb is None:
            raise ValueError("Result database not present")
        if realtime:
            if key in self.__rdb.nrt:
                raise ValueError("Result is already non-realtime")
            self.__rdb.rt[key] = value
            notifier = self.__rdb.rt[key]
            notifier.kernel_attr_init = False
            return notifier
        else:
            if key in self.__rdb.rt.read:
                raise ValueError("Result is already realtime")
            self.__rdb.nrt[key] = value

    def attr_rtresult(self, key, init_value):
        """Writes the value of a real-time result and sets the corresponding
        ``Notifier`` as attribute. The names of the result and of the
        attribute are the same."""
        setattr(self, key, set_result(key, init_value, True))

    def get_result(self, key):
        """Retrieves the value of a result.

        There is no difference between real-time and non-real-time results
        (this function does not return ``Notifier`` instances).
        """
        if self.__rdb is None:
            raise ValueError("Result database not present")
        return self.__rdb.get(key)


class Experiment:
    """Base class for experiments.

    Deriving from this class enables automatic experiment discovery in
    Python modules.
    """
    def prepare(self):
        """Entry point for pre-computing data necessary for running the
        experiment.

        Doing such computations outside of ``run`` enables more efficient
        scheduling of multiple experiments that need to access the shared
        hardware during part of their execution.

        This method must not interact with the hardware.
        """
        pass

    def run(self):
        """The main entry point of the experiment.

        This method must be overloaded by the user to implement the main
        control flow of the experiment.

        This method may interact with the hardware.

        The experiment may call the scheduler's ``pause`` method while in
        ``run``.
        """
        raise NotImplementedError

    def analyze(self):
        """Entry point for analyzing the results of the experiment.

        This method may be overloaded by the user to implement the analysis
        phase of the experiment, for example fitting curves.

        Splitting this phase from ``run`` enables tweaking the analysis
        algorithm on pre-existing data, and CPU-bound analyses to be run
        overlapped with the next experiment in a pipelined manner.

        This method must not interact with the hardware.
        """
        pass


class EnvExperiment(Experiment, HasEnvironment):
    pass


def is_experiment(o):
    """Checks if a Python object is an instantiable user experiment."""
    return (isclass(o)
        and issubclass(o, Experiment)
        and o is not Experiment
        and o is not EnvExperiment)
