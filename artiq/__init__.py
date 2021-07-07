from ._version import get_version
__version__ = get_version()
del get_version

import os
__artiq_dir__ = os.path.dirname(os.path.abspath(__file__))
del os
