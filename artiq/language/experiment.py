from inspect import isclass

__all__ = ["Experiment", "has_analyze", "is_experiment"]


class Experiment:
    """Base class for experiments.

    Deriving from this class enables automatic experiment discovery in
    Python modules.
    """
    def run(self):
        """The main entry point of the experiment.

        This method must be overloaded by the user to implement the main
        control flow of the experiment.
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


def has_analyze(experiment):
    """Checks if an experiment instance overloaded its ``analyze`` method."""
    return experiment.analyze.__func__ is not Experiment.analyze


def is_experiment(o):
    """Checks if a Python object is an instantiable experiment."""
    return isclass(o) and issubclass(o, Experiment) and o is not Experiment
