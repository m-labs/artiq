Core language reference
=======================

The most commonly used features from those modules can be imported with ``from artiq.language import *``.

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
