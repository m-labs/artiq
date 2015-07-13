from inspect import isclass


__all__ = ["NoDefault", "FreeValue", "HasEnvironment",
           "Experiment", "EnvExperiment", "is_experiment"]


class NoDefault:
    """Represents the absence of a default value."""
    pass


class FreeValue:
    def __init__(self, default=NoDefault):
        if default is not NoDefault:
            self.default_value = default

    def default(self):
        return self.default_value

    def process(self, x):
        return x

    def describe(self):
        d = {"ty": "FreeValue"}
        if hasattr(self, "default_value"):
            d["default"] = self.default_value
        return d


class HasEnvironment:
    """Provides methods to manage the environment of an experiment (devices,
    parameters, results, arguments)."""
    def __init__(self, dmgr=None, pdb=None, rdb=None, *,
                 param_override=dict(), **kwargs):
        self.requested_args = dict()

        self.__dmgr = dmgr
        self.__pdb = pdb
        self.__rdb = rdb
        self.__param_override = param_override

        self.__kwargs = kwargs
        self.__in_build = True
        self.build()
        self.__in_build = False
        for key in self.__kwargs.keys():
            if key not in self.requested_args:
                raise TypeError("Got unexpected argument: " + key)
        del self.__kwargs

    def build(self):
        raise NotImplementedError

    def dbs(self):
        return self.__dmgr, self.__pdb, self.__rdb

    def get_argument(self, key, processor=None):
        if not self.__in_build:
            raise TypeError("get_argument() should only "
                            "be called from build()")
        if processor is None:
            processor = FreeValue()
        self.requested_args[key] = processor
        try:
            argval = self.__kwargs[key]
        except KeyError:
            return processor.default()
        return processor.process(argval)

    def attr_argument(self, key, processor=None):
        setattr(self, key, self.get_argument(key, processor))

    def get_device(self, key):
        if self.__dmgr is None:
            raise ValueError("Device manager not present")
        return self.__dmgr.get(key)

    def attr_device(self, key):
        setattr(self, key, self.get_device(key))

    def get_parameter(self, key, default=NoDefault):
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
        setattr(self, key, self.get_parameter(key, default))

    def set_parameter(self, key, value):
        if self.__pdb is None:
            raise ValueError("Parameter database not present")
        self.__pdb.set(key, value)

    def set_result(self, key, value, realtime=False):
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
        setattr(self, key, set_result(key, init_value, True))

    def get_result(self, key):
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
