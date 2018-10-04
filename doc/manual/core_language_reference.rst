Core language reference
=======================

The most commonly used features from the ARTIQ language modules and from the core device modules are bundled together in :mod:`artiq.experiment` and can be imported with ``from artiq.experiment import *``.

:mod:`artiq.language.core` module
---------------------------------

.. automodule:: artiq.language.core
    :members:

:mod:`artiq.language.environment` module
----------------------------------------

.. automodule:: artiq.language.environment
    :members:

:mod:`artiq.language.scan` module
----------------------------------------

.. automodule:: artiq.language.scan
    :members:

:mod:`artiq.language.units` module
----------------------------------

This module contains floating point constants that correspond to common physical units (ns, MHz, ...).
They are provided for convenience (e.g write ``MHz`` instead of ``1000000.0``) and code clarity purposes.
