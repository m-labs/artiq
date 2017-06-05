from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

import os
__artiq_dir__ = os.path.dirname(os.path.abspath(__file__))
del os

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
