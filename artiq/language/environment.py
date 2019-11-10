import warnings
from collections import OrderedDict
from inspect import isclass

from sipyco import pyon

from artiq.language import units
from artiq.language.core import rpc


__all__ = ["NoDefault",
           "PYONValue", "BooleanValue", "EnumerationValue",
           "NumberValue", "StringValue",
           "HasEnvironment", "Experiment", "EnvExperiment"]


class NoDefault:
    """Represents the absence of a default value."""
    pass


class DefaultMissing(Exception):
    """Raised by the ``default`` method of argument processors when no default
    value is available."""
    pass


class _SimpleArgProcessor:
    def __init__(self, default=NoDefault):
        # If default is a list, it means multiple defaults are specified, with
        # decreasing priority.
        if isinstance(default, list):
            raise NotImplementedError
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
    def __init__(self, default=NoDefault):
        # Override the _SimpleArgProcessor init, as list defaults are valid
        # PYON values
        if default is not NoDefault:
            self.default_value = default

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

    When ``scale`` is not specified, and the unit is a common one (i.e.
    defined in ``artiq.language.units``), then the scale is obtained from
    the unit using a simple string match. For example, milliseconds (``"ms"``)
    units set the scale to 0.001. No unit (default) corresponds to a scale of
    1.0.

    For arguments with uncommon or complex units, use both the unit parameter
    (a string for display) and the scale parameter (a numerical scale for
    experiments).
    For example, ``NumberValue(1, unit="xyz", scale=0.001)`` will display as
    1 xyz in the GUI window because of the unit setting, and appear as the
    numerical value 0.001 in the code because of the scale setting.

    :param unit: A string representing the unit of the value.
    :param scale: A numerical scaling factor by which the displayed value is
        multiplied when referenced in the experiment.
    :param step: The step with which the value should be modified by up/down
        buttons in a UI. The default is the scale divided by 10.
    :param min: The minimum value of the argument.
    :param max: The maximum value of the argument.
    :param ndecimals: The number of decimals a UI should use.
    """
    def __init__(self, default=NoDefault, unit="", scale=None,
                 step=None, min=None, max=None, ndecimals=2):
        if scale is None:
            if unit == "":
                scale = 1.0
            else:
                try:
                    scale = getattr(units, unit)
                except AttributeError:
                    raise KeyError("Unit {} is unknown, you must specify "
                                   "the scale manually".format(unit))
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


class TraceArgumentManager:
    def __init__(self):
        self.requested_args = OrderedDict()

    def get(self, key, processor, group, tooltip):
        self.requested_args[key] = processor, group, tooltip
        return None


class ProcessArgumentManager:
    def __init__(self, unprocessed_arguments):
        self.unprocessed_arguments = unprocessed_arguments

    def get(self, key, processor, group, tooltip):
        if key in self.unprocessed_arguments:
            r = processor.process(self.unprocessed_arguments[key])
        else:
            r = processor.default()
        return r


class HasEnvironment:
    """Provides methods to manage the environment of an experiment (arguments,
    devices, datasets)."""
    def __init__(self, managers_or_parent, *args, **kwargs):
        self.children = []
        if isinstance(managers_or_parent, tuple):
            self.__device_mgr = managers_or_parent[0]
            self.__dataset_mgr = managers_or_parent[1]
            self.__argument_mgr = managers_or_parent[2]
            self.__scheduler_defaults = managers_or_parent[3]
        else:
            self.__device_mgr = managers_or_parent.__device_mgr
            self.__dataset_mgr = managers_or_parent.__dataset_mgr
            self.__argument_mgr = managers_or_parent.__argument_mgr
            self.__scheduler_defaults = {}
            managers_or_parent.register_child(self)

        self.__in_build = True
        self.build(*args, **kwargs)
        self.__in_build = False

    def register_child(self, child):
        self.children.append(child)

    def call_child_method(self, method, *args, **kwargs):
        """Calls the named method for each child, if it exists for that child,
        in the order of registration.

        :param method: Name of the method to call
        :type method: str
        :param args: Tuple of positional arguments to pass to all children
        :param kwargs: Dict of keyword arguments to pass to all children
        """
        for child in self.children:
            try:
                child_method = getattr(child, method)
            except AttributeError:
                pass
            else:
                child_method(*args, **kwargs)

    def build(self):
        """Should be implemented by the user to request arguments.

        Other initialization steps such as requesting devices may also be
        performed here.

        There are two situations where the requested devices are replaced by
        ``DummyDevice()`` and arguments are set to their defaults (or ``None``)
        instead: when the repository is scanned to build the list of
        available experiments and when the dataset browser ``artiq_browser``
        is used to open or run the analysis stage of an experiment. Do not
        rely on being able to operate on devices or arguments in :meth:`build`.

        Datasets are read-only in this method.

        Leftover positional and keyword arguments from the constructor are
        forwarded to this method. This is intended for experiments that are
        only meant to be executed programmatically (not from the GUI)."""
        pass

    def get_argument(self, key, processor, group=None, tooltip=None):
        """Retrieves and returns the value of an argument.

        This function should only be called from ``build``.

        :param key: Name of the argument.
        :param processor: A description of how to process the argument, such
            as instances of ``BooleanValue`` and ``NumberValue``.
        :param group: An optional string that defines what group the argument
            belongs to, for user interface purposes.
        :param tooltip: An optional string to describe the argument in more
            detail, applied as a tooltip to the argument name in the user
            interface.
        """
        if not self.__in_build:
            raise TypeError("get_argument() should only "
                            "be called from build()")
        return self.__argument_mgr.get(key, processor, group, tooltip)

    def setattr_argument(self, key, processor=None, group=None, tooltip=None):
        """Sets an argument as attribute. The names of the argument and of the
        attribute are the same.

        The key is added to the instance's kernel invariants."""
        setattr(self, key, self.get_argument(key, processor, group, tooltip))
        kernel_invariants = getattr(self, "kernel_invariants", set())
        self.kernel_invariants = kernel_invariants | {key}

    def get_device_db(self):
        """Returns the full contents of the device database."""
        return self.__device_mgr.get_device_db()

    def get_device(self, key):
        """Creates and returns a device driver."""
        return self.__device_mgr.get(key)

    def setattr_device(self, key):
        """Sets a device driver as attribute. The names of the device driver
        and of the attribute are the same.

        The key is added to the instance's kernel invariants."""
        setattr(self, key, self.get_device(key))
        kernel_invariants = getattr(self, "kernel_invariants", set())
        self.kernel_invariants = kernel_invariants | {key}

    @rpc(flags={"async"})
    def set_dataset(self, key, value,
                    broadcast=False, persist=False, archive=True, save=None):
        """Sets the contents and handling modes of a dataset.

        Datasets must be scalars (``bool``, ``int``, ``float`` or NumPy scalar)
        or NumPy arrays.

        :param broadcast: the data is sent in real-time to the master, which
            dispatches it.
        :param persist: the master should store the data on-disk. Implies
            broadcast.
        :param archive: the data is saved into the local storage of the current
            run (archived as a HDF5 file).
        :param save: deprecated.
        """
        if save is not None:
            warnings.warn("set_dataset save parameter is deprecated, "
                          "use archive instead", FutureWarning)
            archive = save
        self.__dataset_mgr.set(key, value, broadcast, persist, archive)

    @rpc(flags={"async"})
    def mutate_dataset(self, key, index, value):
        """Mutate an existing dataset at the given index (e.g. set a value at
        a given position in a NumPy array)

        If the dataset was created in broadcast mode, the modification is
        immediately transmitted.

        If the index is a tuple of integers, it is interpreted as
        ``slice(*index)``.
        If the index is a tuple of tuples, each sub-tuple is interpreted
        as ``slice(*sub_tuple)`` (multi-dimensional slicing)."""
        self.__dataset_mgr.mutate(key, index, value)

    @rpc(flags={"async"})
    def append_to_dataset(self, key, value):
        """Append a value to a dataset.

        The target dataset must be a list (i.e. support ``append()``), and must
        have previously been set from this experiment.

        The broadcast/persist/archive mode of the given key remains unchanged
        from when the dataset was last set. Appended values are transmitted
        efficiently as incremental modifications in broadcast mode."""
        self.__dataset_mgr.append_to(key, value)

    def get_dataset(self, key, default=NoDefault, archive=True):
        """Returns the contents of a dataset.

        The local storage is searched first, followed by the master storage
        (which contains the broadcasted datasets from all experiments) if the
        key was not found initially.

        If the dataset does not exist, returns the default value. If no default
        is provided, raises ``KeyError``.

        By default, datasets obtained by this method are archived into the output
        HDF5 file of the experiment. If an archived dataset is requested more
        than one time (and therefore its value has potentially changed) or is
        modified, a warning is emitted.

        :param archive: Set to ``False`` to prevent archival together with the run's results.
            Default is ``True``
        """
        try:
            return self.__dataset_mgr.get(key, archive)
        except KeyError:
            if default is NoDefault:
                raise
            else:
                return default

    def setattr_dataset(self, key, default=NoDefault, archive=True):
        """Sets the contents of a dataset as attribute. The names of the
        dataset and of the attribute are the same."""
        setattr(self, key, self.get_dataset(key, default, archive))

    def set_default_scheduling(self, priority=None, pipeline_name=None, flush=None):
        """Sets the default scheduling options.

        This function should only be called from ``build``."""
        if not self.__in_build:
            raise TypeError("set_default_scheduling() should only "
                            "be called from build()")

        if priority is not None:
            self.__scheduler_defaults["priority"] = int(priority)
        if pipeline_name is not None:
            self.__scheduler_defaults["pipeline_name"] = pipeline_name
        if flush is not None:
            self.__scheduler_defaults["flush"] = flush


class Experiment:
    """Base class for top-level experiments.

    Deriving from this class enables automatic experiment discovery in
    Python modules.
    """
    def prepare(self):
        """Entry point for pre-computing data necessary for running the
        experiment.

        Doing such computations outside of :meth:`run` enables more efficient
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

        The experiment may call the scheduler's :meth:`pause` method while in
        :meth:`run`.
        """
        raise NotImplementedError

    def analyze(self):
        """Entry point for analyzing the results of the experiment.

        This method may be overloaded by the user to implement the analysis
        phase of the experiment, for example fitting curves.

        Splitting this phase from :meth:`run` enables tweaking the analysis
        algorithm on pre-existing data, and CPU-bound analyses to be run
        overlapped with the next experiment in a pipelined manner.

        This method must not interact with the hardware.
        """
        pass


class EnvExperiment(Experiment, HasEnvironment):
    """Base class for top-level experiments that use the
    :class:`~artiq.language.environment.HasEnvironment` environment manager.

    Most experiments should derive from this class."""
    def prepare(self):
        """This default prepare method calls :meth:`~artiq.language.environment.Experiment.prepare`
        for all children, in the order of registration, if the child has a
        :meth:`~artiq.language.environment.Experiment.prepare` method."""
        self.call_child_method("prepare")


def is_experiment(o):
    """Checks if a Python object is a top-level experiment class."""
    return (isclass(o)
        and issubclass(o, Experiment)
        and o is not Experiment
        and o is not EnvExperiment)
