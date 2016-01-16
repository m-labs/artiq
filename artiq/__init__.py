from artiq import language
from artiq.language import *
from artiq.coredevice.dds import (PHASE_MODE_CONTINUOUS, PHASE_MODE_ABSOLUTE,
                                  PHASE_MODE_TRACKING)

__all__ = []
__all__.extend(language.__all__)
__all__ += ["PHASE_MODE_CONTINUOUS", "PHASE_MODE_ABSOLUTE",
            "PHASE_MODE_TRACKING"]

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
