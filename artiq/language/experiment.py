from inspect import isclass

__all__ = ["Experiment", "is_experiment"]


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


def is_experiment(o):
    """Checks if a Python object is an instantiable experiment."""
    return isclass(o) and issubclass(o, Experiment) and o is not Experiment
