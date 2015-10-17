from artiq.language.environment import *

import logging


__all__ = ["LogExperiment"]


class LogExperiment:
    def init_logger(self):
        """Call this from build() to add a logging level enumeration
        widget, initialize logging globally, and create a logger.

        Your class must also derive from ``HasEnvironment`` (or
        ``EnvExperiment``).

        The created logger is called ``self.logger``."""
        level = self.get_argument("log_level", EnumerationValue(
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]))

        if level is not None:
            logging.basicConfig(level=getattr(logging, level))
            self.logger = logging.getLogger(self.__class__.__name__)
