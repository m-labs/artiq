from collections import OrderedDict
from inspect import isclass

from artiq.protocols import pyon


__all__ = ["NoDefault",
           "PYONValue", "BooleanValue", "EnumerationValue",
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


class PYONValue(_SimpleArgProcessor):
    """An argument that can be any PYON-serializable value."""
    def process(self, x):
        return pyon.decode(x)

    def describe(self):
        d = {"ty": self.__class__.__name__}
        if hasattr(self, "default_value"):
            d["default"] = pyon.encode(self.default_value)
        return d


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
    """An argument that can take a numerical value.

    If ndecimals = 0, scale = 1 and step is integer, then it returns
    an integer value. Otherwise, it returns a floating point value.
    The simplest way to represent an integer argument is
    ``NumberValue(step=1, ndecimals=0)``.

    :param unit: A string representing the unit of the value, for user
        interface (UI) purposes.
    :param scale: The scale of value for UI purposes. The displayed value is
        divided by the scale.
    :param step: The step with which the value should be modified by up/down
        buttons in a UI. The default is the scale divided by 10.
    :param min: The minimum value of the argument.
    :param max: The maximum value of the argument.
    :param ndecimals: The number of decimals a UI should use.
    """
    def __init__(self, default=NoDefault, unit="", scale=1.0,
                 step=None, min=None, max=None, ndecimals=2):
        if step is None:
            step = scale/10.0
        if default is not NoDefault:
            self.default_value = default
        self.unit = unit
        self.scale = scale
        self.step = step
        self.min = min
        self.max = max
        self.ndecimals = ndecimals

    def _is_int(self):
        return (self.ndecimals == 0
                and int(self.step) == self.step
                and self.scale == 1)

    def default(self):
        if not hasattr(self, "default_value"):
            raise DefaultMissing
        if self._is_int():
            return int(self.default_value)
        else:
            return float(self.default_value)

    def process(self, x):
        if self._is_int():
            return int(x)
        else:
            return float(x)

    def describe(self):
        d = {"ty": self.__class__.__name__}
        if hasattr(self, "default_value"):
            d["default"] = self.default_value
        d["unit"] = self.unit
        d["scale"] = self.scale
        d["step"] = self.step
        d["min"] = self.min
        d["max"] = self.max
        d["ndecimals"] = self.ndecimals
        return d


class StringValue(_SimpleArgProcessor):
    """A string argument."""
    pass


class HasEnvironment:
    """Provides methods to manage the environment of an experiment (arguments,
    devices, datasets)."""
    def __init__(self, device_mgr=None, dataset_mgr=None, *, parent=None,
                 default_arg_none=False, enable_processors=False, **kwargs):
        self.requested_args = OrderedDict()

        self.__device_mgr = device_mgr
        self.__dataset_mgr = dataset_mgr
        self.__parent = parent
        self.__default_arg_none = default_arg_none
        self.__enable_processors = enable_processors

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

        Other initialization steps such as requesting devices may also be
        performed here.

        When the repository is scanned, any requested devices and arguments
        are set to ``None``.

        Datasets are read-only in this method.
        """
        raise NotImplementedError

    def managers(self):
        """Returns the device manager and the dataset manager, in this order.

        This is the same order that the constructor takes them, allowing
        sub-objects to be created with this idiom to pass the environment
        around: ::

            sub_object = SomeLibrary(*self.managers())
        """
        return self.__device_mgr, self.__dataset_mgr

    def get_argument(self, key, processor=None, group=None):
        """Retrieves and returns the value of an argument.

        This function should only be called from ``build``.

        :param key: Name of the argument.
        :param processor: A description of how to process the argument, such
            as instances of ``BooleanValue`` and ``NumberValue``.
        :param group: An optional string that defines what group the argument
            belongs to, for user interface purposes.
        """
        if not self.__in_build:
            raise TypeError("get_argument() should only "
                            "be called from build()")
        if self.__parent is not None and key not in self.__kwargs:
            return self.__parent.get_argument(key, processor, group)
        if processor is None:
            processor = PYONValue()
        self.requested_args[key] = processor, group
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
        if self.__enable_processors:
            return processor.process(argval)
        else:
            return argval

    def setattr_argument(self, key, processor=None, group=None):
        """Sets an argument as attribute. The names of the argument and of the
        attribute are the same."""
        setattr(self, key, self.get_argument(key, processor, group))

    def get_device_db(self):
        """Returns the full contents of the device database."""
        if self.__parent is not None:
            return self.__parent.get_device_db()
        if self.__device_mgr is None:
            raise ValueError("Device manager not present")
        return self.__device_mgr.get_device_db()

    def get_device(self, key):
        """Creates and returns a device driver."""
        if self.__parent is not None:
            return self.__parent.get_device(key)
        if self.__device_mgr is None:
            raise ValueError("Device manager not present")
        return self.__device_mgr.get(key)

    def setattr_device(self, key):
        """Sets a device driver as attribute. The names of the device driver
         and of the attribute are the same."""
        setattr(self, key, self.get_device(key))

    def set_dataset(self, key, value,
                    broadcast=False, persist=False, save=True):
        """Sets the contents and handling modes of a dataset.

        Datasets must be scalars (``bool``, ``int``, ``float`` or NumPy scalar)
        or NumPy arrays.

        :param broadcast: the data is sent in real-time to the master, which
            dispatches it.
        :param persist: the master should store the data on-disk. Implies
            broadcast.
        :param save: the data is saved into the local storage of the current
            run (archived as a HDF5 file).
        """
        if self.__parent is not None:
            self.__parent.set_dataset(key, value, broadcast, persist, save)
            return
        if self.__dataset_mgr is None:
            raise ValueError("Dataset manager not present")
        self.__dataset_mgr.set(key, value, broadcast, persist, save)

    def mutate_dataset(self, key, index, value):
        """Mutate an existing dataset at the given index (e.g. set a value at
        a given position in a NumPy array)

        If the dataset was created in broadcast mode, the modification is
        immediately transmitted."""
        if self.__parent is not None:
            self.__parent.mutate_dataset(key, index, value)
        if self.__dataset_mgr is None:
            raise ValueError("Dataset manager not present")
        self.__dataset_mgr.mutate(key, index, value)

    def get_dataset(self, key, default=NoDefault):
        """Returns the contents of a dataset.

        The local storage is searched first, followed by the master storage
        (which contains the broadcasted datasets from all experiments) if the
        key was not found initially.

        If the dataset does not exist, returns the default value. If no default
        is provided, raises ``KeyError``.
        """
        if self.__parent is not None:
            return self.__parent.get_dataset(key, default)
        if self.__dataset_mgr is None:
            raise ValueError("Dataset manager not present")
        try:
            return self.__dataset_mgr.get(key)
        except KeyError:
            if default is NoDefault:
                raise
            else:
                return default

    def setattr_dataset(self, key, default=NoDefault):
        """Sets the contents of a dataset as attribute. The names of the
        dataset and of the attribute are the same."""
        setattr(self, key, self.get_dataset(key, default))


class Experiment:
    """Base class for top-level experiments.

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
    """Base class for top-level experiments that use the ``HasEnvironment``
    environment manager.

    Most experiment should derive from this class."""
    pass


def is_experiment(o):
    """Checks if a Python object is a top-level experiment class."""
    return (isclass(o)
        and issubclass(o, Experiment)
        and o is not Experiment
        and o is not EnvExperiment)
